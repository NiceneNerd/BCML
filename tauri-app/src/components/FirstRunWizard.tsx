import { useState } from "react";
import { Button, Modal, Carousel, Alert, Form } from "react-bootstrap";
import { invoke } from "@tauri-apps/api/core";
import SettingsTab from "./SettingsTab";
import ProgressModal from "./ProgressModal";
import ErrorModal from "./ErrorModal";

interface FirstRunWizardProps {
  show: boolean;
  onComplete: () => void;
}

interface OldSettingsResult {
  exists: boolean;
  message: string;
}

export default function FirstRunWizard({ show, onComplete }: FirstRunWizardProps) {
  const [page, setPage] = useState(0);
  const [oldSettings, setOldSettings] = useState(false);
  const [converted, setConverted] = useState("");
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [settingsValid, setSettingsValid] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [oldMods, setOldMods] = useState(0);
  const [handlingMods, setHandlingMods] = useState(false);
  const [modsHandled, setModsHandled] = useState(false);
  const [handledError, setHandledError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showError, setShowError] = useState(false);
  const [willRead, setWillRead] = useState(false);
  const [showProgress, setShowProgress] = useState(false);
  const [progressStatus, setProgressStatus] = useState("");

  const pageCount = oldMods > 0 ? 5 : 4;

  const goBack = () => {
    const newPage = page - 1;
    setPage(newPage >= 0 ? newPage : 0);
  };

  const goForward = () => {
    if (!settingsLoaded) {
      checkSettings();
    }
    const newPage = page + 1;
    setPage(newPage < pageCount ? newPage : pageCount - 1);
  };

  const checkSettings = async () => {
    try {
      const result = await invoke("check_old_settings") as OldSettingsResult;
      setOldSettings(result.exists);
      setConverted(result.message);
      setSettingsLoaded(true);
    } catch (err) {
      console.error("Failed to check old settings:", err);
      setSettingsLoaded(true);
    }
  };

  const saveSettings = async (settings: any) => {
    try {
      setSavingSettings(true);
      await invoke("save_settings", { settings });
      setSettingsValid(true);
      setSavingSettings(false);
      
      // Check for old mods
      try {
        const modCount = await invoke("get_old_mods_count") as number;
        setOldMods(modCount);
      } catch (err) {
        console.warn("Could not check old mods:", err);
        setOldMods(0);
      }
    } catch (err) {
      setSavingSettings(false);
      setError(`Failed to save settings: ${err}`);
      setShowError(true);
    }
  };

  const handleMods = async (action: "convert" | "delete" | "ignore") => {
    try {
      setHandlingMods(true);
      setHandledError(null);
      
      if (action === "convert") {
        setProgressStatus("Converting old mods...");
        setShowProgress(true);
        await invoke("convert_old_mods");
      } else if (action === "delete") {
        setProgressStatus("Deleting old mods...");
        setShowProgress(true);
        await invoke("delete_old_mods");
      }
      
      setShowProgress(false);
      setModsHandled(true);
    } catch (err) {
      setShowProgress(false);
      setHandledError(String(err));
      setModsHandled(true);
    }
  };

  const openHelp = () => {
    // Open help in external browser or show help modal
    window.open("https://nicenenerd.github.io/BCML/", "_blank");
  };

  const openTutorial = () => {
    window.open("https://www.youtube.com/embed/8gKRifYyA68", "_blank");
  };

  return (
    <>
      <Modal 
        show={show} 
        onHide={() => {}} 
        size="lg" 
        backdrop="static" 
        keyboard={false}
        className="h-100"
      >
        <Modal.Header>
          <Modal.Title>Welcome to BCML</Modal.Title>
        </Modal.Header>
        <Modal.Body className="d-flex flex-column" style={{ height: "60vh" }}>
          <Carousel
            activeIndex={page}
            onSelect={() => {}}
            controls={false}
            indicators={false}
            className="flex-grow-1"
            interval={null}
          >
            {/* Page 0: Welcome */}
            <Carousel.Item>
              <div className="text-center">
                <img
                  src="/vite.svg"
                  alt="BCML Logo"
                  style={{ width: "128px", height: "128px", margin: "2rem 0" }}
                />
                <p className="mt-4 mb-1">
                  Thank you for installing BCML. It appears that this is
                  your first time running it, or you have upgraded from an
                  old version. We'll need to do a few things to get you
                  set up.
                </p>
              </div>
            </Carousel.Item>

            {/* Page 1: Import Settings */}
            <Carousel.Item>
              <h2>
                <i className="material-icons">settings</i> Import Settings
              </h2>
              {settingsLoaded ? (
                oldSettings ? (
                  <div>
                    <p>
                      It looks like you are upgrading from a previous
                      version of BCML. BCML has attempted to import
                      your old settings. Result:
                    </p>
                    <p>{converted}</p>
                  </div>
                ) : (
                  <div>
                    Let's see, it doesn't look like you are upgrading
                    from a previous version of BCML. Alright then, we'll
                    set you up from scratch on the next page.
                  </div>
                )
              ) : (
                <p>Checking for existing settings...</p>
              )}
            </Carousel.Item>

            {/* Page 2: Configure Settings */}
            <Carousel.Item>
              {settingsLoaded && (
                <>
                  {oldSettings ? (
                    <p>
                      Take a look at your imported settings and
                      check that everything seems right.
                    </p>
                  ) : (
                    <div className="d-flex">
                      <p className="flex-grow-1">
                        Take a moment to configure your basic
                        settings. Folders will turn green when
                        valid. If you need help with this, click
                        the buttons to the right for the in-app
                        Help or the YouTube tutorial.
                      </p>
                      <div>
                        <Button
                          size="sm"
                          variant="warning"
                          onClick={openHelp}
                          className="me-2"
                        >
                          <i className="material-icons">help_outline</i>{" "}
                          Help
                        </Button>
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={openTutorial}
                        >
                          <i className="material-icons">play_circle_outline</i>{" "}
                          Tutorial
                        </Button>
                      </div>
                    </div>
                  )}
                  <SettingsTab
                    onError={(error) => {
                      setError(error);
                      setShowError(true);
                    }}
                    onSettingsValid={(valid) => setSettingsValid(valid)}
                    onSaveSettings={saveSettings}
                    isFirstRun={true}
                    saving={savingSettings}
                  />
                </>
              )}
            </Carousel.Item>

            {/* Page 3: Import Mods (conditional) */}
            {oldMods > 0 && (
              <Carousel.Item>
                <h2>
                  <i className="material-icons">double_arrow</i>{" "}
                  Import Mods
                </h2>
                <p>
                  It looks like you have {oldMods} mods
                  from a previous version of BCML. If you like, you
                  can import them into your new BCML version, or you
                  can just delete or ignore them. (Note that ignoring
                  them is not recommended.)
                </p>
                <div className="d-flex mb-2 gap-2">
                  <Button
                    variant="success"
                    size="sm"
                    onClick={() => handleMods("convert")}
                    disabled={handlingMods}
                  >
                    <i className="material-icons">double_arrow</i>{" "}
                    <span>Import</span>
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => handleMods("delete")}
                    disabled={handlingMods}
                  >
                    <i className="material-icons">delete</i>{" "}
                    <span>Delete</span>
                  </Button>
                  <Button
                    variant="warning"
                    size="sm"
                    onClick={() => {
                      setModsHandled(true);
                      setHandlingMods(true);
                    }}
                    disabled={handlingMods}
                  >
                    <i className="material-icons">warning</i>{" "}
                    <span>Ignore</span>
                  </Button>
                </div>
                <div className="d-flex align-items-start mt-2">
                  {handlingMods && (
                    <>
                      {!modsHandled ? (
                        <div className="d-flex align-items-center">
                          <div className="spinner-border spinner-border-sm me-2" role="status" />
                          <div>{"Processing mods..."}</div>
                        </div>
                      ) : handledError ? (
                        <div className="d-flex align-items-center text-danger">
                          <i className="material-icons me-2">error</i>
                          <p>
                            <strong>Uh-oh! {handledError}</strong>
                          </p>
                        </div>
                      ) : (
                        <div className="d-flex align-items-center text-success">
                          <i className="material-icons me-2">check_circle</i>
                          <p>Alright, done!</p>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </Carousel.Item>
            )}

            {/* Final Page: Setup Complete */}
            <Carousel.Item>
              <h2>
                <i className="material-icons">check</i>
                &nbsp;Setup Complete
              </h2>
              <p>
                Alright, it looks like everything is set up. Time to
                start installing mods!
              </p>
              <Alert variant="info">
                <p>
                  If you're a first time BCML user or upgrading from
                  2.8, it's probably worth taking a look at{" "}
                  <strong>the in-app help</strong>, located in the
                  overflow menu. If you run into any problems, first
                  try <strong>the in-app help</strong> and consider{" "}
                  <strong>clicking the Remerge button</strong>.
                </p>
                <Form.Check
                  type="checkbox"
                  label="I will read the help or I already know what I am doing. I will not ask questions if I haven't checked the help first."
                  checked={willRead}
                  onChange={(e) => setWillRead(e.target.checked)}
                  style={{ fontWeight: "bold" }}
                />
              </Alert>
              <h3>Support BCML</h3>
              <p>
                If BCML has been helpful to you, consider supporting its development!
              </p>
            </Carousel.Item>
          </Carousel>
        </Modal.Body>
        <Modal.Footer>
          {page > 0 && (
            <Button 
              variant="secondary" 
              onClick={goBack}
              disabled={savingSettings || handlingMods}
            >
              <i className="material-icons">arrow_back</i>
            </Button>
          )}
          <div className="flex-grow-1"></div>
          {page < pageCount - 1 ? (
            (page === 2 && settingsValid) || page !== 2 ? (
              <Button 
                variant="primary" 
                onClick={goForward}
                disabled={savingSettings || handlingMods}
              >
                <i className="material-icons">arrow_forward</i>
              </Button>
            ) : (
              <Button
                variant="success"
                onClick={() => setSavingSettings(true)}
                disabled={savingSettings || handlingMods}
              >
                <i className="material-icons">save</i>
              </Button>
            )
          ) : (
            <Button
              variant="success"
              onClick={onComplete}
              disabled={!willRead}
              title={!willRead ? "You must check the consent box first." : ""}
            >
              <i className="material-icons">check</i>
            </Button>
          )}
        </Modal.Footer>
      </Modal>

      <ProgressModal
        show={showProgress}
        title="Setting up BCML"
        status={progressStatus}
        onCancel={() => setShowProgress(false)}
      />

      <ErrorModal
        show={showError}
        error={error}
        onClose={() => setShowError(false)}
      />
    </>
  );
}