import { Modal, Button } from "react-bootstrap";

interface AboutModalProps {
  show: boolean;
  onClose: () => void;
  version: string;
}

function AboutModal({ show, onClose, version }: AboutModalProps) {
  return (
    <Modal show={show} onHide={onClose} centered>
      <Modal.Header closeButton>
        <Modal.Title>About BCML</Modal.Title>
      </Modal.Header>
      <Modal.Body className="text-center">
        <div className="mb-3">
          <img 
            src="/logo-smaller.png" 
            alt="BCML Logo" 
            style={{ maxWidth: "100px" }}
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = 'none';
            }}
          />
        </div>
        <h4>BCML v{version}</h4>
        <p className="text-muted">
          BOTW Cross-Platform Mod Loader
        </p>
        <p>
          A mod manager for The Legend of Zelda: Breath of the Wild.
          This Tauri version provides native performance with a modern interface.
        </p>
        <hr />
        <div className="text-start">
          <h6>Migration Features:</h6>
          <ul className="list-unstyled">
            <li>✅ Modern React 19.x frontend</li>
            <li>✅ Native Tauri backend</li>
            <li>✅ Bootstrap 5.x UI</li>
            <li>✅ TypeScript support</li>
            <li>✅ Cross-platform compatibility</li>
            <li>✅ Zero npm vulnerabilities</li>
          </ul>
        </div>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="primary" onClick={onClose}>
          Close
        </Button>
      </Modal.Footer>
    </Modal>
  );
}

export default AboutModal;