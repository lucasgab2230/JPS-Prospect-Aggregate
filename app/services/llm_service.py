"""Unified LLM Service for Contract Data Enhancement

This service consolidates all LLM-related functionality into a single,
comprehensive service that handles both batch and iterative processing
modes without the complexity of multiple inheritance layers.
"""

import json
import re
import threading
import time
from collections.abc import Callable
from datetime import UTC

UTC = UTC
from datetime import datetime
from typing import Any, Literal, Optional

from app.database import db
from app.database.models import LLMOutput, Prospect
from app.services.optimized_prompts import (
    get_naics_prompt,
    get_title_prompt,
    get_value_prompt,
)
from app.services.set_aside_standardization import (
    SetAsideStandardizer,
    StandardSetAside,
)
from app.utils.llm_utils import call_ollama
from app.utils.logger import logger
from app.utils.naics_lookup import get_naics_description, validate_naics_code

EnhancementType = Literal["all", "values", "titles", "naics", "set_asides"]


class LLMService:
    """Unified LLM service for all contract data enhancement needs.

    This service handles:
    - Individual prospect enhancement (real-time)
    - Batch processing of multiple prospects
    - NAICS classification using LLM
    - Contract value parsing
    - Title enhancement
    - Set-aside standardization
    - Progress tracking and callbacks
    """

    def __init__(self, model_name: str = "qwen3:latest", batch_size: int = 50):
        self.model_name = model_name
        self.batch_size = batch_size
        self.set_aside_standardizer = SetAsideStandardizer()

        # For iterative processing
        self._processing = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._progress: dict[str, any] = {
            "status": "idle",
            "current_type": None,
            "processed": 0,
            "total": 0,
            "current_prospect": None,
            "started_at": None,
            "errors": [],
        }
        self._lock = threading.Lock()
        self._emit_callback: Callable | None = None

    # =============================================================================
    # UTILITY FUNCTIONS (from llm_service_utils.py)
    # =============================================================================

    def ensure_extra_is_dict(self, prospect: Prospect) -> None:
        """Ensure prospect.extra is a dictionary."""
        if not prospect.extra:
            prospect.extra = {}
        elif isinstance(prospect.extra, str):
            try:
                prospect.extra = json.loads(prospect.extra)
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    f"Failed to parse extra field as JSON for prospect {prospect.id}, resetting to empty dict"
                )
                prospect.extra = {}

        if not isinstance(prospect.extra, dict):
            logger.warning(
                f"Extra field is not a dict for prospect {prospect.id}, resetting to empty dict"
            )
            prospect.extra = {}

    def update_prospect_timestamps(self, prospect: Prospect) -> None:
        """Update prospect's ollama processing timestamps and model version."""
        try:
            prospect.ollama_processed_at = datetime.now(UTC)
            prospect.ollama_model_version = self.model_name
        except Exception as e:
            logger.error(f"Failed to update prospect timestamps: {e}")

    def emit_field_update(
        self, prospect_id: str, field_type: str, field_data: dict[str, Any]
    ) -> None:
        """Emit a real-time field update event for a prospect."""
        if not self._emit_callback:
            return

        try:
            self._emit_callback(
                "field_update",
                {
                    "prospect_id": prospect_id,
                    "field_type": field_type,
                    "fields": field_data,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
        except Exception as e:
            logger.error(f"Failed to emit field update: {e}")

    # =============================================================================
    # CORE LLM ENHANCEMENT METHODS
    # =============================================================================

    def parse_existing_naics(self, naics_str: str | None) -> dict[str, str | None]:
        """Parse existing NAICS codes from source data formats and standardize them."""
        if not naics_str:
            return {"code": None, "description": None, "standardized_format": None}

        naics_str = str(naics_str).strip()

        # Handle TBD placeholder values from data sources
        if naics_str.upper() in ["TBD", "TO BE DETERMINED", "N/A", "NA"]:
            return {"code": None, "description": None, "standardized_format": None}

        # Handle numeric NAICS codes with decimal points (e.g., "336510.0" -> "336510")
        if re.match(r"^[1-9]\d{5}\.0+$", naics_str):
            naics_str = naics_str.split(".")[0]

        # Handle different NAICS formats from source data
        patterns = [
            (r"(\d{6})\s*\|\s*(.*)", "pipe"),
            (r"(\d{6})\s*:\s*(.*)", "colon"),
            (r"(\d{6})\s*-\s*(.*)", "hyphen"),
            (r"(\d{6})\s+([^0-9].*)", "space"),
            (r"(\d{6})$", "code_only"),
        ]

        for pattern, format_type in patterns:
            match = re.match(pattern, naics_str)
            if match:
                code = match.group(1)
                description = (
                    match.group(2).strip()
                    if len(match.groups()) > 1 and match.group(2)
                    else None
                )

                if not description:
                    description = get_naics_description(code)

                standardized_format = f"{code} | {description}" if description else code

                return {
                    "code": code,
                    "description": description,
                    "standardized_format": standardized_format,
                    "original_format": format_type,
                }

        # Fallback for unexpected formats
        description = None
        if validate_naics_code(naics_str):
            description = get_naics_description(naics_str)

        standardized_format = (
            f"{naics_str} | {description}" if description else naics_str
        )

        return {
            "code": naics_str,
            "description": description,
            "standardized_format": standardized_format,
            "original_format": "unknown",
        }

    def extract_naics_from_extra_field(self, extra_data: Any) -> dict[str, str | None]:
        """Extract NAICS information from the extra field JSON data."""
        if not extra_data:
            return {"code": None, "description": None, "found_in_extra": False}

        if isinstance(extra_data, str):
            try:
                extra_data = json.loads(extra_data)
            except (json.JSONDecodeError, TypeError):
                return {"code": None, "description": None, "found_in_extra": False}

        if not isinstance(extra_data, dict):
            return {"code": None, "description": None, "found_in_extra": False}

        code = None
        description = None

        # Check for various NAICS field patterns
        if "naics_code" in extra_data and extra_data["naics_code"]:
            potential_code = str(extra_data["naics_code"]).strip()
            if re.match(r"^\d{6}$", potential_code):
                code = potential_code
                description = None
        elif "primary_naics" in extra_data and extra_data["primary_naics"]:
            primary_naics = str(extra_data["primary_naics"]).strip()
            if primary_naics.upper() != "TBD":
                parsed = self.parse_existing_naics(primary_naics)
                code = parsed["code"]
                description = parsed["description"]

        # Fallback: Search for other common NAICS field names
        if not code:
            naics_keys = [
                "naics",
                "industry_code",
                "classification",
                "sector",
                "naics_primary",
            ]
            for key in naics_keys:
                if key in extra_data and extra_data[key]:
                    potential_value = str(extra_data[key]).strip()

                    if potential_value.upper() in [
                        "TBD",
                        "TO BE DETERMINED",
                        "N/A",
                        "NULL",
                        "",
                    ]:
                        continue

                    parsed = self.parse_existing_naics(potential_value)
                    if parsed["code"]:
                        code = parsed["code"]
                        description = parsed["description"]
                        break

        # Last resort: Search all values for 6-digit numbers
        if not code:
            for key, value in extra_data.items():
                if isinstance(value, (str, int)):
                    value_str = str(value)
                    matches = re.findall(r"\b(\d{6})\b", value_str)
                    for potential_code in matches:
                        if potential_code[0] in "123456789":
                            parsed = self.parse_existing_naics(value_str)
                            if parsed["code"] == potential_code:
                                code = parsed["code"]
                                description = parsed["description"]
                                break
                            code = potential_code
                            break

                if code:
                    break

        found_in_extra = code is not None
        return {
            "code": code,
            "description": description,
            "found_in_extra": found_in_extra,
        }

    def _log_llm_output(
        self,
        prospect_id: str,
        enhancement_type: str,
        prompt: str,
        response: str,
        parsed_result: dict,
        success: bool,
        error_message: str = None,
        processing_time: float = None,
    ):
        """Log LLM output to database."""
        try:
            output = LLMOutput(
                prospect_id=prospect_id,
                enhancement_type=enhancement_type,
                prompt=prompt,
                response=response,
                parsed_result=parsed_result,
                success=success,
                error_message=error_message,
                processing_time=processing_time,
            )
            db.session.add(output)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to log LLM output: {e}")
            db.session.rollback()

    def classify_naics_with_llm(
        self,
        title: str,
        description: str,
        prospect_id: str = None,
        agency: str = None,
        contract_type: str = None,
        set_aside: str = None,
        estimated_value: str = None,
        additional_info: str = None,
    ) -> dict:
        """NAICS Classification using LLM with all available prospect information."""
        prompt = get_naics_prompt(
            title=title,
            description=description,
            agency=agency,
            contract_type=contract_type,
            set_aside=set_aside,
            estimated_value=estimated_value,
            additional_info=additional_info,
        )

        start_time = time.time()
        response = call_ollama(prompt, self.model_name)
        processing_time = time.time() - start_time

        try:
            # Clean response of any think tags
            cleaned_response = response
            if response:
                cleaned_response = re.sub(
                    r"<think>.*?</think>", "", response, flags=re.DOTALL | re.IGNORECASE
                ).strip()

            if not cleaned_response:
                self._log_llm_output(
                    prospect_id,
                    "naics_classification",
                    prompt,
                    response,
                    "[]",
                    False,
                    "Empty response after cleaning",
                    processing_time,
                )
                return {
                    "code": None,
                    "description": None,
                    "confidence": 0.0,
                    "all_codes": [],
                }

            parsed = json.loads(cleaned_response)

            if not isinstance(parsed, list):
                raise ValueError("LLM response must be an array of NAICS codes")

            codes = sorted(parsed, key=lambda x: x.get("confidence", 0), reverse=True)

            # Process each code and get official description
            processed_codes = []
            for code_info in codes[:3]:  # Limit to top 3
                code = code_info.get("code")
                if code and validate_naics_code(code):
                    official_description = get_naics_description(code)
                    processed_codes.append(
                        {
                            "code": code,
                            "description": official_description,
                            "confidence": code_info.get("confidence", 0.8),
                        }
                    )

            primary = (
                processed_codes[0]
                if processed_codes
                else {"code": None, "description": None, "confidence": 0.0}
            )
            result = {
                "code": primary.get("code"),
                "description": primary.get("description"),
                "confidence": primary.get("confidence", 0.0),
                "all_codes": processed_codes,
            }

            if prospect_id:
                self._log_llm_output(
                    prospect_id=prospect_id,
                    enhancement_type="naics_classification",
                    prompt=prompt,
                    response=response,
                    parsed_result=result,
                    success=True,
                    processing_time=processing_time,
                )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse NAICS classification response: {e}")
            error_message = f"JSON parse error: {str(e)}"

            if prospect_id:
                self._log_llm_output(
                    prospect_id=prospect_id,
                    enhancement_type="naics_classification",
                    prompt=prompt,
                    response=response,
                    parsed_result={},
                    success=False,
                    error_message=error_message,
                    processing_time=processing_time,
                )

            return {
                "code": None,
                "description": None,
                "confidence": 0.0,
                "all_codes": [],
            }
        except Exception as e:
            logger.error(f"Error in NAICS classification: {e}")
            return {
                "code": None,
                "description": None,
                "confidence": 0.0,
                "all_codes": [],
            }

    def parse_contract_value_with_llm(
        self, value_text: str, prospect_id: str = None
    ) -> dict[str, float | None]:
        """Parse contract value text using LLM for intelligent understanding."""
        prompt = get_value_prompt(value_text)

        start_time = time.time()
        response = call_ollama(prompt, self.model_name)
        processing_time = time.time() - start_time

        try:
            cleaned_response = response
            if response:
                cleaned_response = re.sub(
                    r"<think>.*?</think>", "", response, flags=re.DOTALL | re.IGNORECASE
                ).strip()

            if not cleaned_response:
                self._log_llm_output(
                    prospect_id,
                    "value_parsing",
                    prompt,
                    response,
                    "[]",
                    False,
                    "Empty response after cleaning",
                    processing_time,
                )
                return {"single": None, "min": None, "max": None, "confidence": 0.0}

            parsed = json.loads(cleaned_response)

            result = {
                "single": float(parsed.get("single"))
                if parsed.get("single") is not None
                else None,
                "min": float(parsed.get("min"))
                if parsed.get("min") is not None
                else None,
                "max": float(parsed.get("max"))
                if parsed.get("max") is not None
                else None,
                "confidence": parsed.get("confidence", 1.0),
            }

            # Validate the results
            for key in ["single", "min", "max"]:
                if result[key] is not None and result[key] < 0:
                    result[key] = None

            if prospect_id:
                self._log_llm_output(
                    prospect_id=prospect_id,
                    enhancement_type="value_parsing",
                    prompt=prompt,
                    response=response,
                    parsed_result=result,
                    success=True,
                    processing_time=processing_time,
                )

            return result

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse value response: {e}")

            if prospect_id:
                self._log_llm_output(
                    prospect_id=prospect_id,
                    enhancement_type="value_parsing",
                    prompt=prompt,
                    response=response,
                    parsed_result={},
                    success=False,
                    error_message=str(e),
                    processing_time=processing_time,
                )

            return {"single": None, "min": None, "max": None, "confidence": 0.0}

    def enhance_title_with_llm(
        self, title: str, description: str, agency: str = "", prospect_id: str = None
    ) -> dict[str, Any]:
        """Enhance a prospect title to be clearer and more descriptive."""
        prompt = get_title_prompt(title, description, agency)

        start_time = time.time()
        response = call_ollama(prompt, self.model_name)
        processing_time = time.time() - start_time

        try:
            cleaned_response = response
            if response:
                cleaned_response = re.sub(
                    r"<think>.*?</think>", "", response, flags=re.DOTALL | re.IGNORECASE
                ).strip()

            if not cleaned_response:
                self._log_llm_output(
                    prospect_id,
                    "title_enhancement",
                    prompt,
                    response,
                    "[]",
                    False,
                    "Empty response after cleaning",
                    processing_time,
                )
                return {"enhanced_title": None, "confidence": 0.0, "reasoning": ""}

            parsed = json.loads(cleaned_response)

            result = {
                "enhanced_title": parsed.get("enhanced_title", "").strip(),
                "confidence": parsed.get("confidence", 0.8),
                "reasoning": parsed.get("reasoning", ""),
            }

            # Validate that we got an actual enhancement
            if not result["enhanced_title"] or result["enhanced_title"] == title:
                result["enhanced_title"] = None
                result["confidence"] = 0.0

            if prospect_id:
                self._log_llm_output(
                    prospect_id=prospect_id,
                    enhancement_type="title_enhancement",
                    prompt=prompt,
                    response=response,
                    parsed_result=result,
                    success=True,
                    processing_time=processing_time,
                )

            return result

        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Failed to parse title enhancement response: {e}")

            if prospect_id:
                self._log_llm_output(
                    prospect_id=prospect_id,
                    enhancement_type="title_enhancement",
                    prompt=prompt,
                    response=response,
                    parsed_result={},
                    success=False,
                    error_message=str(e),
                    processing_time=processing_time,
                )

            return {"enhanced_title": None, "confidence": 0.0, "reasoning": ""}

    def standardize_set_aside_with_llm(
        self, set_aside_text: str, prospect_id: str = None, prospect: "Prospect" = None
    ) -> StandardSetAside | None:
        """Standardize set-aside values using LLM-based classification."""
        comprehensive_data = self._get_comprehensive_set_aside_data(
            set_aside_text, prospect
        )

        if not comprehensive_data or not comprehensive_data.strip():
            return StandardSetAside.NOT_AVAILABLE

        try:
            llm_result = self._classify_set_aside_with_llm(
                comprehensive_data, prospect_id
            )
            if llm_result:
                if prospect_id:
                    logger.info(
                        f"LLM set-aside classification for prospect {prospect_id}: '{comprehensive_data}' -> {llm_result.code}"
                    )
                return llm_result

            logger.warning(
                f"LLM classification failed for set-aside '{comprehensive_data}', defaulting to N/A"
            )
            return StandardSetAside.NOT_AVAILABLE

        except Exception as e:
            logger.error(
                f"Error in LLM set-aside classification for '{comprehensive_data}': {e}"
            )
            return StandardSetAside.NOT_AVAILABLE

    def _get_comprehensive_set_aside_data(
        self, set_aside_text: str, prospect: Optional["Prospect"] = None
    ) -> str:
        """Gather comprehensive set-aside data from all available sources."""
        main_set_aside = (set_aside_text or "").strip()

        additional_data = ""
        field_found = None
        if prospect and prospect.extra and isinstance(prospect.extra, dict):
            small_business_program = prospect.extra.get(
                "original_small_business_program", ""
            ).strip()
            if small_business_program and small_business_program.lower() not in [
                "none",
                "n/a",
                "tbd",
                "",
            ]:
                additional_data = small_business_program
                field_found = "original_small_business_program"

        if field_found:
            logger.info(
                f"Found additional set-aside data in field '{field_found}': '{additional_data}'"
            )

        # Combine data sources intelligently
        if main_set_aside and additional_data:
            if main_set_aside.lower() != additional_data.lower():
                comprehensive_data = f"Set-aside: {main_set_aside}; Small Business Program: {additional_data}"
                logger.info(f"Combined set-aside data: '{comprehensive_data}'")
                return comprehensive_data
            logger.info(f"Same data in both sources, using: '{main_set_aside}'")
            return main_set_aside
        if main_set_aside:
            logger.info(f"Using main set_aside field: '{main_set_aside}'")
            return main_set_aside
        if additional_data:
            comprehensive_data = f"Small Business Program: {additional_data}"
            logger.info(f"Using additional data source: '{comprehensive_data}'")
            return comprehensive_data
        logger.info("No meaningful set-aside data found in any source")
        return ""

    def _classify_set_aside_with_llm(
        self, set_aside_text: str, prospect_id: str = None
    ) -> StandardSetAside | None:
        """Use LLM to intelligently classify set-aside values into standardized categories."""
        try:
            prompt = self.set_aside_standardizer.get_llm_prompt().format(set_aside_text)

            start_time = time.time()
            response = call_ollama(prompt, self.model_name)
            processing_time = time.time() - start_time

            if not response:
                logger.warning(
                    f"LLM call failed for set-aside classification: '{set_aside_text}'"
                )

                if prospect_id:
                    self._log_llm_output(
                        prospect_id=prospect_id,
                        enhancement_type="set_aside_standardization",
                        prompt=prompt,
                        response="",
                        parsed_result={},
                        success=False,
                        error_message="LLM call failed - no response received",
                        processing_time=processing_time,
                    )
                return None

            response_text = self._clean_llm_response(response)
            result = self._match_response_to_enum(response_text, set_aside_text)

            if result:
                logger.info(
                    f"LLM classified set-aside '{set_aside_text}' as {result.code}"
                )

                if prospect_id:
                    self._log_llm_output(
                        prospect_id=prospect_id,
                        enhancement_type="set_aside_standardization",
                        prompt=prompt,
                        response=response,
                        parsed_result={
                            "standardized_code": result.code,
                            "standardized_label": result.label,
                            "original_input": set_aside_text,
                            "llm_response": response_text,
                        },
                        success=True,
                        processing_time=processing_time,
                    )

                return result

            logger.warning(
                f"LLM returned unrecognized set-aside classification: '{response_text}' for input '{set_aside_text}'"
            )

            if prospect_id:
                self._log_llm_output(
                    prospect_id=prospect_id,
                    enhancement_type="set_aside_standardization",
                    prompt=prompt,
                    response=response,
                    parsed_result={
                        "llm_response": response_text,
                        "original_input": set_aside_text,
                    },
                    success=False,
                    error_message=f"Unrecognized LLM response: '{response_text}'",
                    processing_time=processing_time,
                )

            return None

        except Exception as e:
            logger.error(
                f"Error in LLM set-aside classification for '{set_aside_text}': {e}"
            )

            if prospect_id:
                self._log_llm_output(
                    prospect_id=prospect_id,
                    enhancement_type="set_aside_standardization",
                    prompt=prompt if "prompt" in locals() else "",
                    response=response if "response" in locals() else "",
                    parsed_result={"original_input": set_aside_text},
                    success=False,
                    error_message=str(e),
                    processing_time=time.time() - start_time
                    if "start_time" in locals()
                    else None,
                )

            return None

    def _clean_llm_response(self, response: str) -> str:
        """Clean LLM response to extract just the classification result."""
        response = response.strip()

        # Remove common LLM artifacts
        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
        response = re.sub(r"<thinking>.*?</thinking>", "", response, flags=re.DOTALL)

        # Keep only the first line if it's a category
        lines = [line.strip() for line in response.split("\n") if line.strip()]
        if lines:
            response = lines[0]

        return response.strip()

    def _match_response_to_enum(
        self, response_text: str, original_input: str
    ) -> StandardSetAside | None:
        """Match LLM response to StandardSetAside enum with fuzzy matching."""
        if not response_text:
            return None

        # First try exact match (case-insensitive)
        for set_aside_type in StandardSetAside:
            if set_aside_type.value.lower() == response_text.lower():
                return set_aside_type

        # Try fuzzy matching for common variations
        response_lower = response_text.lower()

        if "small business" in response_lower or response_lower == "small":
            return StandardSetAside.SMALL_BUSINESS
        if (
            "8(a)" in response_lower
            or "eight a" in response_lower
            or response_lower == "8a"
        ):
            return StandardSetAside.EIGHT_A
        if "hubzone" in response_lower or "hub zone" in response_lower:
            return StandardSetAside.HUBZONE
        if "women" in response_lower and "owned" in response_lower:
            return StandardSetAside.WOMEN_OWNED
        if "veteran" in response_lower and "owned" in response_lower:
            return StandardSetAside.VETERAN_OWNED
        if "full and open" in response_lower or response_lower == "unrestricted":
            return StandardSetAside.FULL_AND_OPEN
        if "sole source" in response_lower:
            return StandardSetAside.SOLE_SOURCE
        if response_lower in ["n/a", "na", "not available", "none", "unknown"]:
            return StandardSetAside.NOT_AVAILABLE

        return None

    # =============================================================================
    # SINGLE PROSPECT ENHANCEMENT
    # =============================================================================

    def enhance_single_prospect(
        self,
        prospect: Prospect,
        enhancement_type: EnhancementType = "all",
        progress_callback: Callable | None = None,
        force_redo: bool = False,
    ) -> dict[str, bool]:
        """Process all enhancements for a single prospect.

        Args:
            prospect: The prospect to enhance
            enhancement_type: Type of enhancement to perform
            progress_callback: Optional callback for progress updates
            force_redo: If True, re-process even if fields already exist

        Returns:
            Dict with enhancement results for each type
        """
        logger.info(
            f"LLM Service: Starting enhance_single_prospect for {prospect.id[:8]}... (type: {enhancement_type}, force_redo: {force_redo})"
        )

        results = {
            "values": False,
            "naics": False,
            "titles": False,
            "set_asides": False,
        }

        # Ensure extra is a dict
        logger.debug(
            f"LLM Service: Ensuring extra field is dict for {prospect.id[:8]}..."
        )
        self.ensure_extra_is_dict(prospect)
        logger.debug(f"LLM Service: Extra field verified for {prospect.id[:8]}...")

        # Convert enhancement_type to list for easier checking
        if isinstance(enhancement_type, str):
            enhancement_types = (
                [t.strip() for t in enhancement_type.split(",")]
                if "," in enhancement_type
                else [enhancement_type]
            )
        else:
            enhancement_types = [enhancement_type]

        # Process title enhancement FIRST (to match frontend order)
        if "titles" in enhancement_types or "all" in enhancement_types:
            logger.info(f"LLM Service: Processing titles for {prospect.id[:8]}...")
            if progress_callback:
                progress_callback(
                    {
                        "status": "processing",
                        "field": "titles",
                        "prospect_id": prospect.id,
                    }
                )

            if prospect.title and (not prospect.ai_enhanced_title or force_redo):
                enhanced_title = self.enhance_title_with_llm(
                    prospect.title,
                    prospect.description or "",
                    prospect.agency or "",
                    prospect_id=prospect.id,
                )

                if enhanced_title["enhanced_title"]:
                    prospect.ai_enhanced_title = enhanced_title["enhanced_title"]

                    prospect.extra["llm_title_enhancement"] = {
                        "confidence": enhanced_title["confidence"],
                        "reasoning": enhanced_title.get("reasoning", ""),
                        "original_title": prospect.title,
                        "enhanced_at": datetime.now(UTC).isoformat(),
                        "model_used": self.model_name,
                    }
                    results["titles"] = True

            # Emit completion callback for titles
            if progress_callback:
                progress_callback(
                    {
                        "status": "completed",
                        "field": "titles",
                        "prospect_id": prospect.id,
                    }
                )
        else:
            logger.debug(
                f"LLM Service: Skipping titles processing for {prospect.id[:8]}"
            )

        # Process value enhancement SECOND (to match frontend order)
        if "values" in enhancement_types or "all" in enhancement_types:
            logger.info(f"LLM Service: Processing values for {prospect.id[:8]}...")
            if progress_callback:
                progress_callback(
                    {
                        "status": "processing",
                        "field": "values",
                        "prospect_id": prospect.id,
                    }
                )

            value_to_parse = None
            if prospect.estimated_value_text and (
                not prospect.estimated_value_single or force_redo
            ):
                value_to_parse = prospect.estimated_value_text
            elif prospect.estimated_value and (
                not prospect.estimated_value_single or force_redo
            ):
                value_to_parse = str(prospect.estimated_value)

            logger.debug(
                f"LLM Service: Value to parse for {prospect.id[:8]}: {value_to_parse}"
            )

            if value_to_parse:
                logger.info(
                    f"LLM Service: Calling parse_contract_value_with_llm for {prospect.id[:8]}..."
                )
                parsed_value = self.parse_contract_value_with_llm(
                    value_to_parse, prospect_id=prospect.id
                )
                logger.info(
                    f"LLM Service: Received parsed value for {prospect.id[:8]}: {parsed_value}"
                )
                # Handle both single values and ranges
                if parsed_value["single"] is not None or (
                    parsed_value["min"] is not None and parsed_value["max"] is not None
                ):
                    # Set single value if available
                    if parsed_value["single"] is not None:
                        prospect.estimated_value_single = float(parsed_value["single"])
                        prospect.estimated_value_min = (
                            float(parsed_value["min"])
                            if parsed_value["min"] is not None
                            else float(parsed_value["single"])
                        )
                        prospect.estimated_value_max = (
                            float(parsed_value["max"])
                            if parsed_value["max"] is not None
                            else float(parsed_value["single"])
                        )
                    else:
                        # We have a range without a single value
                        prospect.estimated_value_single = None
                        prospect.estimated_value_min = (
                            float(parsed_value["min"])
                            if parsed_value["min"] is not None
                            else None
                        )
                        prospect.estimated_value_max = (
                            float(parsed_value["max"])
                            if parsed_value["max"] is not None
                            else None
                        )

                    if not prospect.estimated_value_text:
                        prospect.estimated_value_text = value_to_parse
                    results["values"] = True
            else:
                logger.debug(f"LLM Service: No value to parse for {prospect.id[:8]}")

            # Emit completion callback for values
            if progress_callback:
                progress_callback(
                    {
                        "status": "completed",
                        "field": "values",
                        "prospect_id": prospect.id,
                    }
                )
        else:
            logger.debug(
                f"LLM Service: Skipping values processing for {prospect.id[:8]}"
            )

        # Process NAICS classification
        if "naics" in enhancement_types or "all" in enhancement_types:
            if progress_callback:
                progress_callback(
                    {
                        "status": "processing",
                        "field": "naics",
                        "prospect_id": prospect.id,
                    }
                )

            if prospect.description and (
                not prospect.naics
                or prospect.naics_source != "llm_inferred"
                or force_redo
            ):
                # Store original NAICS if it exists and hasn't been stored yet
                if prospect.naics and "original_naics" not in prospect.extra:
                    prospect.extra["original_naics"] = prospect.naics
                    prospect.extra["original_naics_description"] = (
                        prospect.naics_description
                    )
                    prospect.extra["original_naics_source"] = (
                        prospect.naics_source or "original"
                    )

                # First check extra field
                extra_naics = self.extract_naics_from_extra_field(prospect.extra)

                if extra_naics["found_in_extra"] and extra_naics["code"]:
                    prospect.naics = extra_naics["code"]
                    prospect.naics_description = extra_naics["description"]
                    prospect.naics_source = "original"

                    prospect.extra["naics_extracted_from_extra"] = {
                        "extracted_at": datetime.now(UTC).isoformat(),
                        "original_code": extra_naics["code"],
                        "original_description": extra_naics["description"],
                    }
                    results["naics"] = True
                else:
                    # Use LLM classification
                    classification = self.classify_naics_with_llm(
                        prospect.title,
                        prospect.description,
                        prospect_id=prospect.id,
                        agency=prospect.agency,
                        contract_type=prospect.contract_type,
                        set_aside=prospect.set_aside,
                        estimated_value=prospect.estimated_value_text,
                    )

                    if classification["code"]:
                        prospect.naics = classification["code"]
                        prospect.naics_description = classification["description"]
                        prospect.naics_source = "llm_inferred"

                        prospect.extra["llm_classification"] = {
                            "naics_confidence": classification["confidence"],
                            "model_used": self.model_name,
                            "classified_at": datetime.now(UTC).isoformat(),
                        }
                        results["naics"] = True

            # Emit completion callback for NAICS
            if progress_callback:
                progress_callback(
                    {
                        "status": "completed",
                        "field": "naics",
                        "prospect_id": prospect.id,
                    }
                )

        # Process set-aside standardization
        if "set_asides" in enhancement_types or "all" in enhancement_types:
            if progress_callback:
                progress_callback(
                    {
                        "status": "processing",
                        "field": "set_asides",
                        "prospect_id": prospect.id,
                    }
                )

            if not prospect.set_aside_standardized or force_redo:
                comprehensive_data = self._get_comprehensive_set_aside_data(
                    prospect.set_aside, prospect
                )
                if comprehensive_data:
                    standardized = self.standardize_set_aside_with_llm(
                        comprehensive_data, prospect_id=prospect.id, prospect=prospect
                    )
                    if standardized:
                        prospect.set_aside_standardized = standardized.code
                        prospect.set_aside_standardized_label = standardized.label

                        prospect.extra["set_aside_standardization"] = {
                            "original_set_aside": prospect.set_aside,
                            "comprehensive_data_used": comprehensive_data,
                            "standardized_at": datetime.now(UTC).isoformat(),
                        }
                        results["set_asides"] = True

            # Emit completion callback for set_asides
            if progress_callback:
                progress_callback(
                    {
                        "status": "completed",
                        "field": "set_asides",
                        "prospect_id": prospect.id,
                    }
                )

        # Update timestamps if any enhancements were made
        if any(results.values()):
            logger.debug(f"LLM Service: Updating timestamps for {prospect.id[:8]}...")
            self.update_prospect_timestamps(prospect)

        logger.info(
            f"LLM Service: Completed enhance_single_prospect for {prospect.id[:8]}... - Results: {results}"
        )
        return results

    # =============================================================================
    # BATCH PROCESSING METHODS
    # =============================================================================

    def enhance_prospects_batch(
        self,
        prospects: list[Prospect],
        enhancement_type: EnhancementType = "all",
        commit_batch_size: int = 100,
        emit_updates: bool = False,
    ) -> int:
        """Enhance multiple prospects in batch mode.

        Args:
            prospects: List of prospects to enhance
            enhancement_type: Type of enhancement to perform
            commit_batch_size: How often to commit changes to database
            emit_updates: Whether to emit real-time updates

        Returns:
            Number of successfully processed prospects
        """
        logger.info(
            f"Starting batch enhancement of {len(prospects)} prospects for {enhancement_type}"
        )
        processed_count = 0

        for i in range(0, len(prospects), self.batch_size):
            batch = prospects[i : i + self.batch_size]
            logger.info(
                f"Processing batch {i // self.batch_size + 1}/{(len(prospects) + self.batch_size - 1) // self.batch_size}"
            )

            for prospect in batch:
                try:
                    results = self.enhance_single_prospect(prospect, enhancement_type)

                    if any(results.values()):
                        processed_count += 1

                        # Emit real-time updates if enabled
                        if emit_updates:
                            self.emit_field_update(
                                prospect.id, enhancement_type, results
                            )

                        # Commit immediately for real-time updates if enabled
                        if emit_updates:
                            try:
                                db.session.commit()
                                logger.debug(
                                    f"Committed enhancement for prospect {prospect.id}"
                                )
                            except Exception as e:
                                logger.error(f"Error committing individual update: {e}")
                                db.session.rollback()
                                continue
                except Exception as e:
                    logger.error(f"Error processing prospect {prospect.id}: {e}")
                    continue

            # Batch commit for non-real-time updates
            if (
                not emit_updates
                and processed_count > 0
                and processed_count % commit_batch_size == 0
            ):
                try:
                    db.session.commit()
                    logger.info(f"Committed {processed_count} enhancements")
                except Exception as e:
                    logger.error(f"Error committing batch: {e}")
                    db.session.rollback()

        # Final commit
        try:
            db.session.commit()
            logger.info(
                f"Completed batch enhancement. Total processed: {processed_count}"
            )
        except Exception as e:
            logger.error(f"Error in final commit: {e}")
            db.session.rollback()

        return processed_count

    # =============================================================================
    # ITERATIVE PROCESSING WITH PROGRESS TRACKING
    # =============================================================================

    def set_emit_callback(self, emit_callback: Callable):
        """Set callback for real-time field updates."""
        self._emit_callback = emit_callback

    def get_progress(self) -> dict[str, any]:
        """Get current processing progress."""
        with self._lock:
            return self._progress.copy()

    def is_processing(self) -> bool:
        """Check if enhancement is currently running."""
        return self._processing

    # Backward compatibility methods for API
    def start_enhancement(
        self, enhancement_type: EnhancementType, skip_existing: bool = True
    ) -> dict[str, any]:
        """Start enhancement processing (alias for start_iterative_enhancement)"""
        return self.start_iterative_enhancement(enhancement_type, skip_existing)

    def stop_enhancement(self) -> dict[str, any]:
        """Stop enhancement processing (alias for stop_iterative_enhancement)"""
        return self.stop_iterative_enhancement()

    def start_iterative_enhancement(
        self, enhancement_type: EnhancementType, skip_existing: bool = True
    ) -> dict[str, any]:
        """Start iterative enhancement processing in background thread."""
        if self._processing:
            return {"status": "error", "message": "Enhancement already in progress"}

        self._processing = True
        self._stop_event.clear()

        # Get prospects to process
        prospects_to_process = self._get_prospects_to_process(
            enhancement_type, skip_existing
        )

        if not prospects_to_process:
            self._processing = False
            return {
                "status": "completed",
                "message": "No prospects need enhancement",
                "total_to_process": 0,
            }

        # Initialize progress
        with self._lock:
            self._progress.update(
                {
                    "status": "running",
                    "current_type": enhancement_type,
                    "processed": 0,
                    "total": len(prospects_to_process),
                    "current_prospect": None,
                    "started_at": datetime.now(UTC).isoformat(),
                    "errors": [],
                }
            )

        # Start processing thread
        self._thread = threading.Thread(
            target=self._iterative_processing_worker,
            args=(prospects_to_process, enhancement_type),
        )
        self._thread.daemon = True
        self._thread.start()

        return {
            "status": "started",
            "message": f"Started {enhancement_type} enhancement",
            "total_to_process": len(prospects_to_process),
        }

    def stop_iterative_enhancement(self) -> dict[str, any]:
        """Stop the current iterative enhancement process."""
        if not self._processing:
            return {"status": "error", "message": "No enhancement currently running"}

        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        with self._lock:
            self._progress["status"] = "stopped"

        self._processing = False

        return {"status": "stopped", "message": "Enhancement process stopped"}

    def _get_prospects_to_process(
        self, enhancement_type: EnhancementType, skip_existing: bool = True
    ) -> list[Prospect]:
        """Get list of prospects that need processing for the given enhancement type."""
        query = Prospect.query

        if skip_existing:
            if enhancement_type == "values":
                query = query.filter(Prospect.estimated_value_single.is_(None))
            elif enhancement_type == "naics":
                query = query.filter(
                    (Prospect.naics.is_(None))
                    | (Prospect.naics_source != "llm_inferred")
                )
            elif enhancement_type == "titles":
                query = query.filter(Prospect.ai_enhanced_title.is_(None))
            elif enhancement_type == "set_asides":
                query = query.filter(Prospect.set_aside_standardized.is_(None))
            # For "all", we don't filter - we'll check each type individually

        return query.all()

    def _iterative_processing_worker(
        self, prospects: list[Prospect], enhancement_type: EnhancementType
    ):
        """Worker thread for iterative processing."""
        try:
            for i, prospect in enumerate(prospects):
                if self._stop_event.is_set():
                    break

                with self._lock:
                    self._progress["current_prospect"] = prospect.id

                try:
                    results = self.enhance_single_prospect(prospect, enhancement_type)

                    if any(results.values()):
                        db.session.commit()
                        self.emit_field_update(prospect.id, enhancement_type, results)

                    with self._lock:
                        self._progress["processed"] = i + 1

                except Exception as e:
                    logger.error(f"Error processing prospect {prospect.id}: {e}")
                    with self._lock:
                        self._progress["errors"].append(
                            {
                                "prospect_id": prospect.id,
                                "error": str(e),
                                "timestamp": datetime.now(UTC).isoformat(),
                            }
                        )

                # Small delay to prevent overwhelming the system
                time.sleep(0.1)

            # Mark as completed
            with self._lock:
                if not self._stop_event.is_set():
                    self._progress["status"] = "completed"
                else:
                    self._progress["status"] = "stopped"

        except Exception as e:
            logger.error(f"Error in iterative processing worker: {e}")
            with self._lock:
                self._progress["status"] = "failed"
                self._progress["errors"].append(
                    {
                        "error": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
        finally:
            self._processing = False


# Global instance for backward compatibility
llm_service = LLMService()
