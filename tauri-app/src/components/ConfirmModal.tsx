import { Modal, Button } from "react-bootstrap";

interface ConfirmModalProps {
  show: boolean;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  title?: string;
}

function ConfirmModal({ show, message, onConfirm, onCancel, title = "Please Confirm" }: ConfirmModalProps) {
  return (
    <Modal show={show} onHide={onCancel}>
      <Modal.Header closeButton>
        <Modal.Title>{title}</Modal.Title>
      </Modal.Header>
      <Modal.Body>{message}</Modal.Body>
      <Modal.Footer>
        <Button variant="primary" onClick={() => {
          onConfirm();
          onCancel();
        }}>
          OK
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </Modal.Footer>
    </Modal>
  );
}

export default ConfirmModal;