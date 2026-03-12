import { Modal, Spinner, ProgressBar } from "react-bootstrap";

interface ProgressModalProps {
  show: boolean;
  title: string;
  status?: string;
  progress?: number;
  onCancel?: () => void;
}

function ProgressModal({ show, title, status, progress, onCancel }: ProgressModalProps) {
  return (
    <Modal 
      show={show} 
      backdrop="static" 
      keyboard={false}
      centered
      size="sm"
    >
      <Modal.Header>
        <Modal.Title>{title}</Modal.Title>
      </Modal.Header>
      <Modal.Body className="text-center">
        <Spinner animation="border" role="status" className="mb-3">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
        {status && (
          <div className="mb-3">
            <p className="mb-1">{status}</p>
          </div>
        )}
        {typeof progress === 'number' && (
          <ProgressBar now={progress} label={`${progress}%`} />
        )}
      </Modal.Body>
      {onCancel && (
        <Modal.Footer>
          <button 
            type="button" 
            className="btn btn-secondary"
            onClick={onCancel}
          >
            Cancel
          </button>
        </Modal.Footer>
      )}
    </Modal>
  );
}

export default ProgressModal;