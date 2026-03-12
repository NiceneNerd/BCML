import { Modal, Button } from "react-bootstrap";

interface DoneModalProps {
  show: boolean;
  onClose: () => void;
  onLaunchGame?: () => void;
  hasCemu?: boolean;
}

function DoneModal({ show, onClose, onLaunchGame, hasCemu }: DoneModalProps) {
  return (
    <Modal show={show} size="sm" centered onHide={onClose}>
      <Modal.Header closeButton>
        <Modal.Title>Done!</Modal.Title>
      </Modal.Header>
      <Modal.Footer>
        <Button variant="primary" onClick={onClose}>
          OK
        </Button>
        {hasCemu && onLaunchGame && (
          <Button variant="secondary" onClick={() => {
            onLaunchGame();
            onClose();
          }}>
            Launch Game
          </Button>
        )}
      </Modal.Footer>
    </Modal>
  );
}

export default DoneModal;