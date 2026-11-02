interface Window {
  showToast?: (props: {
    title: string;
    message: string;
    type?: 'success' | 'error' | 'info';
    duration?: number;
  }) => string;
}
