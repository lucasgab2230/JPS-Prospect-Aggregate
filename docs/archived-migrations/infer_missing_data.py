import logging
import re  # Import regex module
import sqlite3
import sys
import time
from pathlib import Path

# --- Path Setup ---
# Add project root to sys.path if needed
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app import create_app  # Import create_app
from app.utils.llm_utils import call_ollama

# --- End Path Setup ---

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Configuration ---


# --- Helper function to get DB path from app config ---
def get_db_path_from_app_config(app):
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    if not db_uri or not db_uri.startswith("sqlite:///"):
        raise ValueError(
            f"SQLALCHEMY_DATABASE_URI is not configured correctly in the app: {db_uri}"
        )

    # Extract path from URI. Assumes "sqlite:///absolute/path" or "sqlite:///relative/path"
    db_path_str = db_uri.split("///", 1)[1]

    # If the path is relative, it's relative to the instance folder
    if not Path(db_path_str).is_absolute():
        return Path(app.instance_path) / db_path_str
    return Path(db_path_str)


# Define which columns in 'prospects' we want to check for missing data
# And which corresponding column in 'inferred_prospect_data' to update
# Format: (prospects_col, inferred_col, prompt_template)
FIELDS_TO_INFER = [
    (
        "requirement_title",
        "inferred_requirement_title",
        """Given the following description, generate a concise requirement title (max 15 words):

Description: {description}""",
    ),
    (
        "contract_type",
        "inferred_contract_type",
        """Based on the title and description, suggest a likely contract type (e.g., FFP, T&M, IDIQ, BPA, Other):

Title: {title}
Description: {description}""",
    ),
    # Add more fields as needed...
    # Example: ('naics', 'inferred_naics', "Infer the most likely NAICS code based on: Title={title}, Desc={description}"),
    # Example: ('award_date', 'inferred_award_date', "Estimate the award date based on: Title={title}, Desc={description}, SolicitationDate={solicitation_date}")
]
BATCH_SIZE = 10  # Smaller batch size might be better with multi-LLM calls
RATE_LIMIT_DELAY = 2  # Seconds to wait between *individual* LLM calls
# LLM Configuration
MODEL_NAMES = [
    "deepseek-r1:14b",
    "gemma3:27b",
    "qwen3:14b",
]  # Models for voting/generation
GENERATION_MODEL_INDEX = (
    0  # Index of the model in MODEL_NAMES used for primary generation
)
MAX_RETRIES = (
    1  # Max number of times to retry generation/voting if the post-check fails
)

# Voting Prompts (Instruct models to output ONLY "yes" or "no")
# Note: {context_str} will be dynamically created based on available data
PRE_CHECK_PROMPT_TEMPLATE = """
Based on the following information, is it likely that a meaningful value for '{target_field}' can be inferred? Respond ONLY with 'yes' or 'no'.

Context:
{context_str}
"""

POST_CHECK_PROMPT_TEMPLATE = """
Given the following context, is the proposed value for '{target_field}' plausible? Respond ONLY with 'yes' or 'no'.

Context:
{context_str}

Proposed Value: {inferred_value}
"""

# --- Helper Function for Cleaning LLM Output ---


def _clean_llm_response(response_text: str | None) -> str | None:
    """Removes text within <think>...</think> tags from the LLM response."""
    if not response_text:
        return None

    # Use regex to remove <think>...</think> blocks, ignoring case and handling multiline content
    cleaned_text = re.sub(
        r"<think>.*?</think>", "", response_text, flags=re.DOTALL | re.IGNORECASE
    )

    # Return the cleaned text, stripping leading/trailing whitespace
    # Return None if the string becomes empty after cleaning
    cleaned_text = cleaned_text.strip()
    return cleaned_text if cleaned_text else None


# --- Helper Function for Voting ---


def get_llm_vote(prompt: str, models: list[str], delay: int) -> bool:
    """Gets votes from multiple LLMs on a given prompt. Requires a simple majority ('yes') to pass.
    Strips <think> tags before evaluating votes.

    Args:
        prompt: The prompt to send to each voting LLM.
        models: A list of Ollama model names to use for voting.
        delay: Seconds to wait between individual LLM calls.

    Returns:
        True if a majority voted 'yes', False otherwise.
    """
    yes_votes = 0
    total_votes = len(models)
    if total_votes == 0:
        logger.warning("No models provided for voting.")
        return False  # Cannot vote without models

    logger.debug(f"Initiating vote with {total_votes} models...")
    for model_name in models:
        try:
            logger.debug(f"Requesting vote from model: {model_name}")
            raw_response = call_ollama(prompt, model_name)
            time.sleep(delay)  # Apply rate limit between each call

            # Clean the response before processing the vote
            cleaned_response = _clean_llm_response(raw_response)

            if cleaned_response:
                vote = cleaned_response.lower()  # Use cleaned response
                logger.debug(f"Model {model_name} voted (after cleaning): '{vote}'")
                if "yes" in vote:  # Simple check for 'yes'
                    yes_votes += 1
            else:
                # Safely format the log message, handling None
                raw_response_preview = (
                    f"'{raw_response[:100]}...'" if raw_response else "None"
                )
                logger.warning(
                    f"Model {model_name} did not provide a usable response (after cleaning) for voting. Raw: {raw_response_preview}"
                )
                # Consider how to handle non-responses (e.g., treat as 'no' or exclude)
                # Currently, it just doesn't count as a 'yes'

        except Exception as e:
            logger.error(
                f"Error getting vote from model {model_name}: {e}", exc_info=False
            )
            # Continue to next model, treat error as non-'yes' vote

    required_votes = (total_votes // 2) + 1
    logger.debug(
        f"Vote result: {yes_votes} 'yes' votes out of {total_votes} (required: {required_votes})"
    )
    return yes_votes >= required_votes


# --- Main Logic ---
def infer_missing_prospect_data():
    """Reads prospects, identifies missing data, calls LLM for inference with voting/retries, and updates inferred table."""
    app = create_app()  # Create a Flask app instance
    with app.app_context():  # Push an application context
        DB_PATH = get_db_path_from_app_config(app)  # Get DB_PATH from app config

        if not DB_PATH.exists():
            # Try to create the instance directory if it doesn't exist, as SQLite might be there
            if app.instance_path and not Path(app.instance_path).exists():
                try:
                    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created instance directory: {app.instance_path}")
                except Exception as e:
                    logger.error(
                        f"Failed to create instance directory {app.instance_path}: {e}"
                    )
            # Re-check if DB_PATH exists after attempting to create instance folder
            if not DB_PATH.exists():
                logger.error(
                    f"Database not found at {DB_PATH} even after checking instance path. Exiting."
                )
                return

        conn = None  # Initialize conn outside try block
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row  # Access columns by name
            cursor = conn.cursor()
            logger.info(f"Connected to database: {DB_PATH}")

            generation_model = MODEL_NAMES[GENERATION_MODEL_INDEX]

            for (
                prospects_col,
                inferred_col,
                generation_prompt_template,
            ) in FIELDS_TO_INFER:
                logger.info(
                    f"--- Processing missing data for: {prospects_col} -> {inferred_col} ---"
                )

                select_sql = f"""
                SELECT p.id, p.requirement_title, p.requirement_description, p.solicitation_date
                FROM prospects p
                LEFT JOIN inferred_prospect_data ipd ON p.id = ipd.prospect_id
                WHERE (p.{prospects_col} IS NULL OR p.{prospects_col} = '')
                AND (ipd.{inferred_col} IS NULL OR ipd.{inferred_col} = '')
                """

                cursor.execute(select_sql)
                prospects_to_process = cursor.fetchall()
                total_prospects = len(prospects_to_process)
                logger.info(
                    f"Found {total_prospects} prospects potentially needing inference for '{inferred_col}'."
                )

                total_processed_successfully = 0
                total_skipped_pre_check = 0
                total_failed_post_check = 0

                # Process in batches
                for i in range(0, total_prospects, BATCH_SIZE):
                    batch = prospects_to_process[i : i + BATCH_SIZE]
                    batch_number = i // BATCH_SIZE + 1
                    logger.info(
                        f"Processing batch {batch_number} for {inferred_col} (size: {len(batch)})"
                    )

                    for row in batch:
                        prospect_id = row["id"]
                        logger.debug(
                            f"Processing Prospect ID: {prospect_id} for field '{inferred_col}'"
                        )

                        # 1. Prepare Context (for voting and generation)
                        # Create a simple string representation of the context for voting prompts
                        context_dict = {
                            "title": row["requirement_title"],
                            "description": row["requirement_description"],
                            "solicitation_date": row["solicitation_date"],
                            # Add other relevant fields from SELECT if needed
                        }
                        context_str_parts = [
                            f"{k}: {v}" for k, v in context_dict.items() if v
                        ]
                        context_str = (
                            "\n".join(context_str_parts)
                            if context_str_parts
                            else "No context available."
                        )

                        # Clean context dict for generation prompt formatting (replace None with '')
                        generation_context = {
                            k: v if v is not None else ""
                            for k, v in context_dict.items()
                        }

                        # 2. Pre-check Vote
                        pre_check_prompt = PRE_CHECK_PROMPT_TEMPLATE.format(
                            target_field=inferred_col, context_str=context_str
                        )
                        logger.debug(
                            f"Performing pre-check vote for {prospect_id} ({inferred_col})..."
                        )
                        proceed_vote = get_llm_vote(
                            pre_check_prompt, MODEL_NAMES, RATE_LIMIT_DELAY
                        )

                        if not proceed_vote:
                            logger.info(
                                f"Skipping prospect {prospect_id} ({inferred_col}) due to failed pre-check vote."
                            )
                            total_skipped_pre_check += 1
                            continue  # Skip to the next prospect in the batch

                        logger.debug(
                            f"Pre-check vote passed for {prospect_id} ({inferred_col}). Proceeding to generation."
                        )

                        # 3. Generation and Post-check Loop (with retries)
                        inferred_value = None
                        update_successful = False
                        for attempt in range(
                            MAX_RETRIES + 1
                        ):  # Initial attempt + MAX_RETRIES
                            # 3a. Generate Inference
                            generation_prompt = generation_prompt_template.format(
                                **generation_context
                            )
                            logger.debug(
                                f"Attempt {attempt + 1}: Generating value for {prospect_id} ({inferred_col}) using {generation_model}..."
                            )

                            raw_inferred_value = call_ollama(
                                generation_prompt, generation_model
                            )

                            # Clean the generated value
                            current_inferred_value = _clean_llm_response(
                                raw_inferred_value
                            )

                            if not current_inferred_value:
                                logger.warning(
                                    f"Attempt {attempt + 1}: Generation failed or produced empty result after cleaning for {prospect_id} ({inferred_col}). Raw: '{raw_inferred_value[:100]}...'"
                                )
                                # If generation fails, don't retry post-check, just break retry loop if needed
                                if attempt >= MAX_RETRIES:
                                    logger.error(
                                        f"Final generation attempt failed for {prospect_id} ({inferred_col})."
                                    )
                                    total_failed_post_check += (
                                        1  # Count as failed post-check overall
                                    )
                                continue  # Try generation again if retries remain

                            logger.debug(
                                f"Attempt {attempt + 1}: Generated value (cleaned) for {prospect_id} ({inferred_col}): {current_inferred_value[:100]}..."
                            )

                            # 3b. Post-check Vote
                            post_check_prompt = POST_CHECK_PROMPT_TEMPLATE.format(
                                target_field=inferred_col,
                                context_str=context_str,
                                inferred_value=current_inferred_value,
                            )
                            logger.debug(
                                f"Attempt {attempt + 1}: Performing post-check vote for {prospect_id} ({inferred_col})..."
                            )
                            validation_vote = get_llm_vote(
                                post_check_prompt, MODEL_NAMES, RATE_LIMIT_DELAY
                            )

                            if validation_vote:
                                logger.info(
                                    f"Post-check vote PASSED for {prospect_id} ({inferred_col}) on attempt {attempt + 1}."
                                )
                                inferred_value = (
                                    current_inferred_value  # Accept this value
                                )
                                update_successful = True
                                break  # Exit retry loop, value is validated
                            logger.warning(
                                f"Post-check vote FAILED for {prospect_id} ({inferred_col}) on attempt {attempt + 1}. Inferred value: '{current_inferred_value[:100]}...'"
                            )
                            if attempt >= MAX_RETRIES:
                                logger.error(
                                    f"Post-check vote failed after final attempt for {prospect_id} ({inferred_col}). Discarding value."
                                )
                                total_failed_post_check += 1
                                # else: loop continues for retry

                        # 4. Update Database if Successful
                        if update_successful and inferred_value:
                            try:
                                upsert_sql = f"""
                                INSERT INTO inferred_prospect_data (prospect_id, {inferred_col}, inferred_by_model)
                                VALUES (?, ?, ?)
                                ON CONFLICT(prospect_id) DO UPDATE SET
                                {inferred_col}=excluded.{inferred_col},
                                inferred_by_model=excluded.inferred_by_model,
                                inferred_at=CURRENT_TIMESTAMP;
                                """
                                cursor.execute(
                                    upsert_sql,
                                    (prospect_id, inferred_value, generation_model),
                                )
                                conn.commit()  # Commit after each successful prospect update
                                total_processed_successfully += (
                                    1  # Increment total count
                                )
                                logger.info(
                                    f"Successfully inferred, updated, and committed {inferred_col} for prospect {prospect_id}."
                                )
                            except sqlite3.Error as db_err:
                                logger.error(
                                    f"Database error updating prospect {prospect_id} ({inferred_col}): {db_err}"
                                )
                                logger.warning("Attempting rollback...")
                                try:
                                    conn.rollback()  # Rollback the single failed transaction
                                except sqlite3.Error as rb_err:
                                    logger.error(f"Rollback failed: {rb_err}")
                                # Decide if this should stop the batch or just log and continue
                        # else: logging for failed attempts already handled within the loop

                        # Optional: Short delay even between prospects within a batch?
                        # time.sleep(0.5)

                    # Commit after each batch if updates were made -- REMOVED
                    # if batch_updates_made > 0:
                    #    conn.commit()
                    #    logger.info(f"Committed batch {batch_number} for {inferred_col}. Updated {batch_updates_made} prospects in this batch.")
                    #    total_processed_successfully += batch_updates_made
                    # else:
                    #    logger.info(f"No updates committed in batch {batch_number} for {inferred_col}.")

                    logger.info(
                        f"Finished processing batch {batch_number} for {inferred_col}."
                    )  # Log end of batch

                logger.info(f"Finished processing for {prospects_col}. Summary:")
                logger.info(
                    f"  Total prospects found needing inference: {total_prospects}"
                )
                logger.info(
                    f"  Successfully inferred and committed across all fields: {total_processed_successfully}"
                )
                logger.info(
                    f"  Skipped due to failed pre-check vote: {total_skipped_pre_check}"
                )
                logger.info(
                    f"  Failed post-check validation (after retries): {total_failed_post_check}"
                )
                # Note: total_prospects = success + skipped + failed (approximately, barring errors)

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            if conn:  # Attempt to rollback if there was an error mid-transaction
                try:
                    conn.rollback()
                    logger.warning("Database transaction rolled back due to error.")
                except sqlite3.Error as rb_err:
                    logger.error(f"Error during rollback: {rb_err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        finally:
            if conn:
                conn.close()
                logger.info("Database connection closed.")


if __name__ == "__main__":
    logger.info("Starting LLM inference script with voting/retry logic...")
    # This allows the script to be run directly
    # Create app and push context for the main execution
    app = create_app()
    with app.app_context():
        infer_missing_prospect_data()
        logger.info("LLM inference script finished.")
