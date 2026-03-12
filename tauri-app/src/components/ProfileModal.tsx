import { useState, useEffect } from "react";
import { Modal, Button, Form, InputGroup, ButtonGroup } from "react-bootstrap";
import { invoke } from "@tauri-apps/api/core";

interface Profile {
  name: string;
  path: string;
}

interface ProfileModalProps {
  show: boolean;
  onClose: () => void;
  busy: boolean;
  onSave: (profile: { name: string }, operation: string) => void;
  onLoad: (profile: Profile, operation: string) => void;
  onDelete: (profile: Profile, operation: string) => void;
}

function ProfileModal({ 
  show, 
  onClose, 
  busy, 
  onSave, 
  onLoad, 
  onDelete 
}: ProfileModalProps) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [currentProfile, setCurrentProfile] = useState<Profile | null>(null);
  const [profileName, setProfileName] = useState("");

  useEffect(() => {
    if (show) {
      refreshProfiles();
    }
  }, [show]);

  const refreshProfiles = async () => {
    try {
      // TODO: Implement get_profiles and get_current_profile commands in Tauri
      const profileList = await invoke("get_profiles") as Profile[];
      const current = await invoke("get_current_profile") as Profile | null;
      setProfiles(profileList);
      setCurrentProfile(current);
      setProfileName("");
    } catch (error) {
      console.error("Failed to load profiles:", error);
      // Fallback to empty list
      setProfiles([]);
      setCurrentProfile(null);
    }
  };

  const handleSaveProfile = () => {
    if (profileName.trim()) {
      onSave({ name: profileName.trim() }, "save");
    }
  };

  return (
    <Modal 
      show={show} 
      onHide={onClose}
      style={{ opacity: busy ? 0.5 : 1 }}
    >
      <Modal.Header closeButton>
        <Modal.Title>Mod Profiles</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <h6>
          <strong>Current Profile:</strong>{" "}
          {currentProfile?.name || <i>None</i>}
        </h6>
        
        <InputGroup className="mb-3">
          <Form.Control
            placeholder="New profile name"
            value={profileName}
            onChange={(e) => setProfileName(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSaveProfile()}
          />
          <Button
            variant="primary"
            onClick={handleSaveProfile}
            disabled={!profileName.trim()}
          >
            Save
          </Button>
        </InputGroup>
        
        <h6>Available Profiles</h6>
        {profiles.length > 0 ? (
          profiles.map((profile) => (
            <div
              key={profile.path}
              className="d-flex flex-row align-items-center mb-2"
            >
              <span>{profile.name}</span>
              <div className="flex-grow-1"></div>
              <ButtonGroup size="sm">
                <Button
                  variant="success"
                  onClick={() => onLoad(profile, "load")}
                  title="Load Profile"
                >
                  🔄
                </Button>
                <Button
                  variant="danger"
                  onClick={() => onDelete(profile, "delete")}
                  title="Delete Profile"
                >
                  🗑️
                </Button>
              </ButtonGroup>
            </div>
          ))
        ) : (
          <p className="text-muted">No profiles yet</p>
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

export default ProfileModal;