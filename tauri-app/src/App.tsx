import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Container, Navbar, Tab, Tabs, Dropdown, Button, OverlayTrigger, Tooltip } from "react-bootstrap";
import ModsTab from "./components/ModsTab";
import SettingsTab from "./components/SettingsTab";
import DevToolsTab from "./components/DevToolsTab";
import ProgressModal from "./components/ProgressModal";
import DoneModal from "./components/DoneModal";
import ConfirmModal from "./components/ConfirmModal";
import ErrorModal from "./components/ErrorModal";
import BackupModal from "./components/BackupModal";
import ProfileModal from "./components/ProfileModal";
import AboutModal from "./components/AboutModal";
import FirstRunWizard from "./components/FirstRunWizard";
import "bootstrap/dist/css/bootstrap.min.css";
import "./App.css";

const TABS = ["mods", "dev-tools", "settings"];

function App() {
  const [activeTab, setActiveTab] = useState("mods");
  const [version, setVersion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [hasCemu, setHasCemu] = useState(false);
  const [showFirstRun, setShowFirstRun] = useState(false);
  
  // Modal states
  const [showProgress, setShowProgress] = useState(false);
  const [progressTitle, setProgressTitle] = useState("");
  const [progressStatus, setProgressStatus] = useState("");
  const [showDone, setShowDone] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmMessage, setConfirmMessage] = useState("");
  const [confirmCallback, setConfirmCallback] = useState<(() => void) | null>(null);
  const [showError, setShowError] = useState(false);
  const [showBackups, setShowBackups] = useState(false);
  const [showProfiles, setShowProfiles] = useState(false);
  const [showAbout, setShowAbout] = useState(false);

  useEffect(() => {
    // Check if we're running in Tauri context
    if (typeof window !== 'undefined' && (window as any).__TAURI__) {
      // Check for first run before doing anything else
      invoke("check_settings_exist")
        .then((exists: any) => {
          const isFirstRun = !exists;
          setShowFirstRun(isFirstRun);
          if (exists) {
            // Only do these checks if not first run
            // Get version from Rust backend
            invoke("get_version")
              .then((ver) => setVersion(ver as string))
              .catch((err) => setError(`Failed to get version: ${err}`));

            // Perform sanity check
            invoke("sanity_check")
              .then((result) => {
                if (!(result as boolean)) {
                  setError("Sanity check failed");
                }
              })
              .catch((err) => setError(`Sanity check failed: ${err}`));

            // Check if Cemu is available
            invoke("get_settings")
              .then((settings: any) => {
                setHasCemu(!!settings.cemu_dir);
              })
              .catch(() => setHasCemu(false));
          } else {
            // First run - just get version
            invoke("get_version")
              .then((ver) => setVersion(ver as string))
              .catch((err) => setError(`Failed to get version: ${err}`));
          }
        })
        .catch((err) => {
          console.error("Failed to check settings:", err);
          setError(`Failed to check settings: ${err}`);
        });
    } else {
      // Running in browser for development - simulate first run
      setVersion("3.10.8 (dev)");
      setHasCemu(true);
      // Show first-run wizard in development
      setShowFirstRun(true);
    }
  }, []);

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.ctrlKey && e.key === "Tab") {
      e.preventDefault();
      const currentIndex = TABS.indexOf(activeTab);
      const nextIndex = (currentIndex + 1) % TABS.length;
      setActiveTab(TABS[nextIndex]);
    }
    if (e.key === "F5") {
      e.preventDefault();
      window.location.reload();
    }
    if (e.key === "F1") {
      e.preventDefault();
      openHelp();
    }
  };

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [activeTab]);

  // Helper functions
  const showErrorDialog = (errorMsg: string | { short?: string; error_text?: string }) => {
    const errorString = typeof errorMsg === 'string' 
      ? errorMsg 
      : errorMsg.short || errorMsg.error_text || 'An unknown error occurred';
    setError(errorString);
    setShowError(true);
  };

  const showProgressDialog = (title: string, status?: string) => {
    setProgressTitle(title);
    setProgressStatus(status || "");
    setShowProgress(true);
  };

  const showDoneDialog = () => {
    setShowProgress(false);
    setShowDone(true);
  };

  const confirm = (message: string, callback: () => void) => {
    setConfirmMessage(message);
    setConfirmCallback(() => callback);
    setShowConfirm(true);
  };

  const openHelp = () => {
    // TODO: Open help documentation
    console.log("Help functionality not yet implemented");
  };

  const saveModList = async () => {
    try {
      showProgressDialog("Saving Mod List");
      // TODO: Implement save_mod_list command
      await invoke("save_mod_list");
      showDoneDialog();
    } catch (err) {
      showErrorDialog(`Failed to save mod list: ${err}`);
    }
  };

  const updateBcml = () => {
    confirm(
      "Are you sure you want to update BCML? " +
      "Updating will close the program, run the update, and attempt to launch it again.",
      async () => {
        try {
          // TODO: Implement update_bcml command
          await invoke("update_bcml");
        } catch (err) {
          showErrorDialog(`Failed to update BCML: ${err}`);
        }
      }
    );
  };

  const runSetupWizard = () => {
    // Show the setup wizard again
    setShowFirstRun(true);
  };

  const onFirstRunComplete = async () => {
    setShowFirstRun(false);
    
    // Now perform the initial setup that was skipped
    try {
      // Get version from Rust backend
      const ver = await invoke("get_version");
      setVersion(ver as string);

      // Perform sanity check
      const result = await invoke("sanity_check");
      if (!(result as boolean)) {
        setError("Sanity check failed");
      }

      // Check if Cemu is available
      const settings = await invoke("get_settings");
      setHasCemu(!!(settings as any).cemu_dir);
    } catch (err) {
      setError(`Failed to complete setup: ${err}`);
    }
  };

  const launchGame = async () => {
    try {
      showProgressDialog("Launching Game");
      // TODO: Implement launch_game command
      await invoke("launch_game");
      showDoneDialog();
    } catch (err) {
      showErrorDialog(`Failed to launch game: ${err}`);
    }
  };

  // Backup handlers
  const handleBackups = async (backup: any, operation: string) => {
    let progressTitle;
    let action;
    if (operation === "create") {
      progressTitle = "Creating Backup";
      action = "create_backup";
    } else if (operation === "restore") {
      progressTitle = `Restoring ${backup.name}`;
      action = "restore_backup";
    } else {
      progressTitle = `Deleting ${backup.name}`;
      action = "delete_backup";
    }

    const task = async () => {
      try {
        if (operation !== "delete") {
          showProgressDialog(progressTitle);
        } else {
          setShowBackups(false);
        }
        
        // TODO: Implement backup commands
        await invoke(action, { backup: typeof backup === 'string' ? backup : backup.path });
        
        if (operation !== "delete") {
          showDoneDialog();
        }
        setShowBackups(operation === "delete");
      } catch (err) {
        showErrorDialog(`Backup operation failed: ${err}`);
      }
    };

    if (operation === "delete") {
      confirm("Are you sure you want to delete this backup?", task);
    } else {
      task();
    }
  };

  const handleOldRestore = async () => {
    try {
      showProgressDialog("Restoring BCML 2.8 Backup");
      setShowBackups(false);
      // TODO: Implement restore_old_backup command
      await invoke("restore_old_backup");
      showDoneDialog();
    } catch (err) {
      showErrorDialog(`Failed to restore old backup: ${err}`);
    }
  };

  // Profile handlers
  const handleProfile = async (profile: any, operation: string) => {
    let progressTitle;
    let action;
    if (operation === "save") {
      progressTitle = `Saving Profile: ${profile.name}`;
      action = "save_profile";
    } else if (operation === "load") {
      progressTitle = `Loading Profile: ${profile.name}`;
      action = "set_profile";
    } else {
      progressTitle = `Deleting Profile: ${profile.name}`;
      action = "delete_profile";
    }

    const task = async () => {
      try {
        if (operation !== "delete") {
          showProgressDialog(progressTitle);
        } else {
          setShowProfiles(false);
        }
        
        // TODO: Implement profile commands
        await invoke(action, { profile });
        
        if (operation !== "delete") {
          showDoneDialog();
        }
        setShowProfiles(operation === "delete");
      } catch (err) {
        showErrorDialog(`Profile operation failed: ${err}`);
      }
    };

    if (operation === "delete") {
      confirm("Are you sure you want to delete this profile?", task);
    } else {
      task();
    }
  };

  if (error) {
    return (
      <Container className="mt-3">
        <div className="alert alert-danger" role="alert">
          <h4 className="alert-heading">Error</h4>
          <p>{error}</p>
        </div>
      </Container>
    );
  }

  return (
    <div className="app">
      <Navbar bg="dark" variant="dark" expand="lg">
        <Container fluid className="position-relative">
          <Navbar.Brand>
            BCML {version && `v${version}`}
          </Navbar.Brand>
          <Navbar.Text>
            BOTW Cross-Platform Mod Loader
          </Navbar.Text>
          
          {/* Overflow Menu */}
          <div className="overflow-menu d-flex">
            <Dropdown align="end">
              <Dropdown.Toggle
                id="dropdown-basic"
                variant="outline-light"
                size="sm"
                title="Overflow Menu (Alt+M)"
                className="dropdown-toggle"
              >
                <i className="material-icons">menu</i>
              </Dropdown.Toggle>
              <Dropdown.Menu>
                <Dropdown.Item onClick={saveModList}>
                  Save Mod List
                </Dropdown.Item>
                <Dropdown.Item onClick={updateBcml}>
                  Update BCML
                </Dropdown.Item>
                <Dropdown.Item onClick={runSetupWizard}>
                  Run Setup Wizard
                </Dropdown.Item>
                <Dropdown.Item onClick={() => setShowAbout(true)}>
                  About
                </Dropdown.Item>
              </Dropdown.Menu>
            </Dropdown>
            
            <OverlayTrigger
              overlay={<Tooltip id="help-tooltip">Help (F1)</Tooltip>}
              placement="bottom"
            >
              <Button
                variant="outline-light"
                size="sm"
                className="ms-2"
                onClick={openHelp}
              >
                <i className="material-icons">help</i>
              </Button>
            </OverlayTrigger>
          </div>
        </Container>
      </Navbar>

      <Tabs
        activeKey={activeTab}
        onSelect={(tab) => setActiveTab(tab || "mods")}
        className="nav-tabs"
      >
        <Tab eventKey="mods" title="Mods">
          <div className="tab-pane active">
            <ModsTab 
              onError={showErrorDialog}
              onProgress={showProgressDialog}
              onDone={showDoneDialog}
              onBackup={() => setShowBackups(true)}
              onProfile={() => setShowProfiles(true)}
              onLaunch={launchGame}
              onConfirm={confirm}
            />
          </div>
        </Tab>
        <Tab eventKey="dev-tools" title="Dev Tools">
          <div className="tab-pane active">
            <DevToolsTab
              onError={showErrorDialog}
              onProgress={showProgressDialog}
              onDone={showDoneDialog}
            />
          </div>
        </Tab>
        <Tab eventKey="settings" title="Settings">
          <div className="tab-pane active">
            <Container fluid className="p-3">
              <SettingsTab
                onError={showErrorDialog}
                onProgress={showProgressDialog}
                onDone={showDoneDialog}
              />
            </Container>
          </div>
        </Tab>
      </Tabs>

      {/* Modals */}
      <ProgressModal
        show={showProgress}
        title={progressTitle}
        status={progressStatus}
        onCancel={() => setShowProgress(false)}
      />
      
      <DoneModal
        show={showDone}
        onClose={() => setShowDone(false)}
        onLaunchGame={hasCemu ? launchGame : undefined}
        hasCemu={hasCemu}
      />
      
      <ConfirmModal
        show={showConfirm}
        message={confirmMessage}
        onConfirm={() => {
          if (confirmCallback) {
            confirmCallback();
          }
          setShowConfirm(false);
          setConfirmCallback(null);
        }}
        onCancel={() => {
          setShowConfirm(false);
          setConfirmCallback(null);
        }}
      />
      
      <ErrorModal
        show={showError}
        error={error}
        onClose={() => {
          setShowError(false);
          setError(null);
        }}
      />
      
      <BackupModal
        show={showBackups}
        onClose={() => setShowBackups(false)}
        busy={showProgress}
        onCreate={handleBackups}
        onRestore={handleBackups}
        onDelete={handleBackups}
        onOldRestore={handleOldRestore}
      />
      
      <ProfileModal
        show={showProfiles}
        onClose={() => setShowProfiles(false)}
        busy={showProgress}
        onSave={handleProfile}
        onLoad={handleProfile}
        onDelete={handleProfile}
      />
      
      <AboutModal
        show={showAbout}
        onClose={() => setShowAbout(false)}
        version={version}
      />
      
      <FirstRunWizard
        show={showFirstRun}
        onComplete={onFirstRunComplete}
      />
    </div>
  );
}

export default App;
