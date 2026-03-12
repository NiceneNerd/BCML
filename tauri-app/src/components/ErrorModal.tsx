import { Modal, Button } from "react-bootstrap";

interface ErrorModalProps {
  show: boolean;
  error: string | { short?: string; error_text?: string } | null;
  onClose: () => void;
}

function ErrorModal({ show, error, onClose }: ErrorModalProps) {
  const errorMessage = typeof error === 'string' 
    ? error 
    : error?.short || error?.error_text || 'An unknown error occurred';

  return (
    <Modal show={show} onHide={onClose}>
      <Modal.Header closeButton>
        <Modal.Title className="text-danger">Error</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <div className="alert alert-danger">
          <pre style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
            {errorMessage}
          </pre>
        </div>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </Modal.Footer>
    </Modal>
  );
}

export default ErrorModal;