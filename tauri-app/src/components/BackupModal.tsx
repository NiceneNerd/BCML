import { useState, useEffect } from "react";
import { Modal, Button, Form, InputGroup, ButtonGroup } from "react-bootstrap";
import { invoke } from "@tauri-apps/api/core";

interface Backup {
  name: string;
  path: string;
  num: number;
}

interface BackupModalProps {
  show: boolean;
  onClose: () => void;
  busy: boolean;
  onCreate: (backupName: string, operation: string) => void;
  onRestore: (backup: Backup, operation: string) => void;
  onDelete: (backup: Backup, operation: string) => void;
  onOldRestore?: () => void;
}

function BackupModal({ 
  show, 
  onClose, 
  busy, 
  onCreate, 
  onRestore, 
  onDelete, 
  onOldRestore 
}: BackupModalProps) {
  const [backups, setBackups] = useState<Backup[]>([]);
  const [backupName, setBackupName] = useState("");

  useEffect(() => {
    if (show) {
      refreshBackups();
    }
  }, [show]);

  const refreshBackups = async () => {
    try {
      // TODO: Implement get_backups command in Tauri
      const backupList = await invoke("get_backups") as Backup[];
      setBackups(backupList);
      setBackupName("");
    } catch (error) {
      console.error("Failed to load backups:", error);
      // Fallback to empty list
      setBackups([]);
    }
  };

  const handleCreateBackup = () => {
    if (backupName.trim()) {
      onCreate(backupName.trim(), "create");
    }
  };

  return (
    <Modal 
      show={show} 
      onHide={onClose}
      style={{ opacity: busy ? 0.5 : 1 }}
    >
      <Modal.Header closeButton>
        <Modal.Title>Backup and Restore Mods</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <p>
          Here you can backup and restore entire mod configurations. 
          The backups are complete and exact: what you restore will be 
          identical to what you backed up.
        </p>
        <hr />
        
        <h6>Create Backup</h6>
        <InputGroup className="mb-3">
          <Form.Control
            placeholder="Backup name"
            value={backupName}
            onChange={(e) => setBackupName(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleCreateBackup()}
          />
          <Button
            variant="primary"
            onClick={handleCreateBackup}
            disabled={!backupName.trim()}
          >
            Create
          </Button>
        </InputGroup>
        
        <hr />
        
        <h6>Restore Backup</h6>
        {backups.length > 0 ? (
          backups.map((backup) => (
            <div
              key={backup.path}
              className="d-flex flex-row align-items-center mb-2"
            >
              <span>
                {backup.name.replace("_", " ")}{" "}
                <small>({backup.num} mods)</small>
              </span>
              <div className="flex-grow-1"></div>
              <ButtonGroup size="sm">
                <Button
                  variant="success"
                  onClick={() => onRestore(backup, "restore")}
                  title="Restore backup"
                >
                  🔄
                </Button>
                <Button
                  variant="danger"
                  onClick={() => onDelete(backup, "delete")}
                  title="Delete backup"
                >
                  🗑️
                </Button>
              </ButtonGroup>
            </div>
          ))
        ) : (
          <p className="text-muted">No backups available</p>
        )}

        {onOldRestore && (
          <>
            <hr />
            <h6>Legacy BCML 2.8 Backup</h6>
            <Button
              variant="warning"
              size="sm"
              onClick={onOldRestore}
            >
              Restore BCML 2.8 Backup
            </Button>
          </>
        )}
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </Modal.Footer>
    </Modal>
  );
}

export default BackupModal;