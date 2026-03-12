import { useState, useEffect } from "react";
import { Button, ButtonGroup, Modal, Form, Dropdown } from "react-bootstrap";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

interface Mod {
  name: string;
  path: string;
  enabled: boolean;
  priority: number;
  description?: string;
  version?: string;
}

interface ModsTabProps {
  onError: (error: string) => void;
  onProgress: (title: string, status?: string) => void;
  onDone: () => void;
  onBackup: () => void;
  onProfile: () => void;
  onLaunch: () => void;
  onConfirm: (message: string, callback: () => void) => void;
}

function ModsTab({
  onError,
  onProgress,
  onDone,
  onBackup,
  onProfile,
  onLaunch,
  onConfirm
}: ModsTabProps) {
  const [mods, setMods] = useState<Mod[]>([]);
  const [selectedMods, setSelectedMods] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [showInstallModal, setShowInstallModal] = useState(false);
  const [installFiles, setInstallFiles] = useState<string[]>([]);
  const [showDisabled, setShowDisabled] = useState(true);
  const [sortReverse, setSortReverse] = useState(true);

  useEffect(() => {
    loadMods();
    
    // Add keyboard shortcuts
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey) {
        switch (e.key) {
          case "i":
            e.preventDefault();
            setShowInstallModal(true);
            break;
          case "d":
            e.preventDefault();
            if (selectedMods.length > 0) handleDisableMods();
            break;
          case "e":
            e.preventDefault();
            if (selectedMods.length > 0) handleEnableMods();
            break;
          case "u":
            e.preventDefault();
            if (e.shiftKey) {
              uninstallAllMods();
            } else if (selectedMods.length > 0) {
              handleUninstallMods();
            }
            break;
          case "x":
            e.preventDefault();
            if (selectedMods.length > 0) exploreModFolders();
            break;
          case "p":
            e.preventDefault();
            if (selectedMods.length > 0) reprocessMods();
            break;
          case "m":
            e.preventDefault();
            remergeAll();
            break;
          case "l":
            e.preventDefault();
            onLaunch();
            break;
          case "h":
            e.preventDefault();
            setShowDisabled(!showDisabled);
            break;
          case "o":
            e.preventDefault();
            setSortReverse(!sortReverse);
            break;
          case "b":
            e.preventDefault();
            onBackup();
            break;
          case "f":
            e.preventDefault();
            onProfile();
            break;
          default:
            break;
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [selectedMods, showDisabled, sortReverse]);

  const loadMods = async () => {
    setLoading(true);
    try {
      // Check if we're running in Tauri context
      if (typeof window !== 'undefined' && (window as any).__TAURI__) {
        const modList = await invoke("get_mods") as Mod[];
        setMods(modList);
      } else {
        // Mock data for browser development
        setMods([
          {
            name: "Example Mod 1",
            path: "/path/to/mod1",
            enabled: true,
            priority: 100,
            description: "An example mod for testing"
          },
          {
            name: "Example Mod 2",
            path: "/path/to/mod2",
            enabled: false,
            priority: 200,
            description: "Another example mod"
          },
          {
            name: "Really Long Mod Name That Should Be Truncated",
            path: "/path/to/mod3",
            enabled: true,
            priority: 300,
            description: "A mod with a very long name to test text truncation in the UI"
          }
        ]);
      }
    } catch (error) {
      console.error("Failed to load mods:", error);
      // Fallback to placeholder data
      setMods([
        {
          name: "Example Mod 1",
          path: "/path/to/mod1",
          enabled: true,
          priority: 100,
          description: "An example mod for testing"
        },
        {
          name: "Example Mod 2",
          path: "/path/to/mod2",
          enabled: false,
          priority: 200,
          description: "Another example mod"
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleModSelect = (modPath: string, selected: boolean) => {
    if (selected) {
      setSelectedMods([...selectedMods, modPath]);
    } else {
      setSelectedMods(selectedMods.filter(path => path !== modPath));
    }
  };

  const handleSelectModFiles = async () => {
    try {
      const selected = await open({
        multiple: true,
        filters: [{
          name: 'Mod Files',
          extensions: ['bnp', 'zip', '7z', 'rar']
        }]
      });
      
      if (selected && Array.isArray(selected)) {
        setInstallFiles(selected);
      } else if (selected) {
        setInstallFiles([selected]);
      }
    } catch (error) {
      console.error("Error selecting mod files:", error);
    }
  };

  const handleInstallSelectedMods = async () => {
    try {
      onProgress("Installing Mod" + (installFiles.length > 1 ? "s" : ""));
      
      // TODO: Implement actual mod installation via Tauri command
      await invoke("install_mod", { 
        mods: installFiles, 
        options: {} 
      });
      
      setInstallFiles([]);
      setShowInstallModal(false);
      await loadMods();
      onDone();
    } catch (error) {
      onError(`Failed to install mods: ${error}`);
    }
  };

  // New functionality methods
  const exploreModFolders = async () => {
    try {
      for (const modPath of selectedMods) {
        await invoke("explore_mod", { mod_path: modPath });
      }
    } catch (error) {
      onError(`Failed to explore mod folders: ${error}`);
    }
  };

  const reprocessMods = async () => {
    try {
      onProgress("Reprocessing Mods");
      for (const modPath of selectedMods) {
        await invoke("reprocess_mod", { mod_path: modPath });
      }
      await loadMods();
      onDone();
    } catch (error) {
      onError(`Failed to reprocess mods: ${error}`);
    }
  };

  const remergeAll = async () => {
    try {
      onProgress("Remerging All Mods");
      await invoke("remerge_all");
      await loadMods();
      onDone();
    } catch (error) {
      onError(`Failed to remerge mods: ${error}`);
    }
  };

  const uninstallAllMods = () => {
    onConfirm(
      "Are you sure you want to uninstall ALL mods? This cannot be undone.",
      async () => {
        try {
          onProgress("Uninstalling All Mods");
          await invoke("uninstall_all_mods");
          await loadMods();
          setSelectedMods([]);
          onDone();
        } catch (error) {
          onError(`Failed to uninstall all mods: ${error}`);
        }
      }
    );
  };

  const exportMods = async () => {
    try {
      onProgress("Exporting Mods");
      await invoke("export_mods");
      onDone();
    } catch (error) {
      onError(`Failed to export mods: ${error}`);
    }
  };

  // Filter and sort mods
  const filteredMods = mods
    .filter(mod => showDisabled || mod.enabled)
    .sort((a, b) => {
      const compareValue = a.priority - b.priority;
      return sortReverse ? -compareValue : compareValue;
    });

  const handleEnableMods = async () => {
    try {
      for (const modPath of selectedMods) {
        await invoke("toggle_mod", { mod_path: modPath, enabled: true });
      }
      await loadMods(); // Refresh mod list
      setSelectedMods([]);
    } catch (error) {
      console.error("Failed to enable mods:", error);
    }
  };

  const handleDisableMods = async () => {
    try {
      for (const modPath of selectedMods) {
        await invoke("toggle_mod", { mod_path: modPath, enabled: false });
      }
      await loadMods(); // Refresh mod list
      setSelectedMods([]);
    } catch (error) {
      console.error("Failed to disable mods:", error);
    }
  };

  const handleUninstallMods = async () => {
    if (!confirm(`Are you sure you want to uninstall ${selectedMods.length} mod(s)?`)) {
      return;
    }
    
    try {
      for (const modPath of selectedMods) {
        await invoke("uninstall_mod", { mod_path: modPath });
      }
      await loadMods(); // Refresh mod list
      setSelectedMods([]);
    } catch (error) {
      console.error("Failed to uninstall mods:", error);
    }
  };

  return (
    <div className="mods-layout">
      {/* Left Panel - Mod List */}
      <div className="mods-panel">
        {loading ? (
          <div className="text-center mt-3">
            <div className="spinner-border spinner-border-sm text-light" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        ) : (
          <>
            <div className="mod-list">
              {filteredMods.length === 0 ? (
                <div className="text-secondary m-2 text-center">
                  {mods.length === 0 
                    ? "No mods installed"
                    : "No mods match current filter"
                  }
                </div>
              ) : (
                <div className="list-group">
                  {filteredMods.map((mod, index) => (
                    <div
                      key={index}
                      className={`list-group-item ${
                        selectedMods.includes(mod.path) ? 'active' : ''
                      } ${
                        !mod.enabled ? 'mod-disabled' : ''
                      }`}
                      onClick={() => handleModSelect(mod.path, !selectedMods.includes(mod.path))}
                      style={{ cursor: 'pointer' }}
                    >
                      <div className="d-flex align-items-center">
                        <div className="mod-handle me-2">
                          <i className="material-icons">drag_indicator</i>
                        </div>
                        <div className="flex-grow-1 text-truncate">
                          <div className="fw-bold text-truncate">{mod.name}</div>
                          <small className="text-muted">{mod.version || "Unknown"}</small>
                        </div>
                        <div className="ms-2">
                          <span className={`badge ${mod.enabled ? 'bg-success' : 'bg-secondary'} badge-sm`}>
                            {mod.enabled ? 'ON' : 'OFF'}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            {/* List Actions */}
            <div className="list-actions d-flex pt-1">
              <div className="btn-group btn-group-xs">
                <Button
                  variant="secondary"
                  size="sm"
                  title={`Current sort priority: ${sortReverse ? 'highest to lowest' : 'lowest to highest'}\nClick to change (Ctrl+O)`}
                  onClick={() => setSortReverse(!sortReverse)}
                >
                  <i className={`material-icons ${!sortReverse ? 'reversed' : ''}`}>sort</i>
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  title="Show sort handles"
                >
                  <i className="material-icons">reorder</i>
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  title={`${showDisabled ? 'Hide' : 'Show'} disabled mods (Ctrl+H)`}
                  onClick={() => setShowDisabled(!showDisabled)}
                >
                  <i className="material-icons">{showDisabled ? 'visibility_off' : 'visibility'}</i>
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  title="Backup & Restore (Ctrl+B)"
                  onClick={onBackup}
                >
                  <i className="material-icons">backup</i>
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  title="Profiles (Ctrl+F)"
                  onClick={onProfile}
                >
                  <i className="material-icons">dynamic_feed</i>
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  title="Export"
                  onClick={exportMods}
                >
                  <i className="material-icons">open_in_browser</i>
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  title="Uninstall all mods (Ctrl+Shift+U)"
                  onClick={uninstallAllMods}
                >
                  <i className="material-icons">delete_sweep</i>
                </Button>
              </div>
              <div className="flex-grow-1"></div>
              <Dropdown as={ButtonGroup} size="sm">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={onLaunch}
                  title="Launch Breath of the Wild (Ctrl+L)"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    viewBox="0 0 171 171"
                    style={{ fill: "#ffb300" }}
                  >
                    <g fill="#ffb300">
                      <path d="M85.5,19.14844l-35.625,61.67578h71.25zM121.125,80.82422l-35.625,61.67578h71.25zM85.5,142.5l-35.625,-61.67578l-35.625,61.67578z"></path>
                    </g>
                  </svg>
                </Button>
                <Dropdown.Toggle split variant="primary" />
                <Dropdown.Menu>
                  <Dropdown.Item>Launch without mods</Dropdown.Item>
                  <Dropdown.Item>Launch Cemu without starting game</Dropdown.Item>
                </Dropdown.Menu>
              </Dropdown>
            </div>
          </>
        )}
      </div>

      {/* Right Panel - Mod Info */}
      <div className="mod-info-panel">
        <div className="mod-content">
          {selectedMods.length === 0 ? (
            <div className="text-center mt-5">
              <h4>No Mod Selected</h4>
              <p className="text-muted">Select a mod from the list to view details</p>
            </div>
          ) : selectedMods.length === 1 ? (
            <div className="p-3">
              <div className="mod-header">
                <div className="mod-title">
                  <h1>{filteredMods.find(m => m.path === selectedMods[0])?.name || 'Unknown Mod'}</h1>
                  <span className={`badge ${filteredMods.find(m => m.path === selectedMods[0])?.enabled ? 'bg-success' : 'bg-secondary'}`}>
                    {filteredMods.find(m => m.path === selectedMods[0])?.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
              </div>
              <div className="mod-descrip">
                <p>{filteredMods.find(m => m.path === selectedMods[0])?.description || 'No description available.'}</p>
              </div>
              <div className="mod-actions">
                <Button
                  variant={filteredMods.find(m => m.path === selectedMods[0])?.enabled ? 'warning' : 'success'}
                  onClick={filteredMods.find(m => m.path === selectedMods[0])?.enabled ? handleDisableMods : handleEnableMods}
                  title={`${filteredMods.find(m => m.path === selectedMods[0])?.enabled ? 'Disable' : 'Enable'} mod`}
                >
                  <i className="material-icons">{filteredMods.find(m => m.path === selectedMods[0])?.enabled ? 'visibility_off' : 'visibility'}</i>
                  <span>{filteredMods.find(m => m.path === selectedMods[0])?.enabled ? 'Disable' : 'Enable'}</span>
                </Button>
                <Button
                  variant="info"
                  onClick={exploreModFolders}
                  title="Open mod folder"
                >
                  <i className="material-icons">folder_open</i>
                  <span>Explore</span>
                </Button>
                <Button
                  variant="secondary"
                  onClick={reprocessMods}
                  title="Reprocess mod"
                >
                  <i className="material-icons">refresh</i>
                  <span>Reprocess</span>
                </Button>
                <Button
                  variant="danger"
                  onClick={handleUninstallMods}
                  title="Uninstall mod"
                >
                  <i className="material-icons">delete</i>
                  <span>Uninstall</span>
                </Button>
              </div>
              <div className="mod-details">
                <span>Version: {filteredMods.find(m => m.path === selectedMods[0])?.version || 'Unknown'}</span>
                <span>Priority: {filteredMods.find(m => m.path === selectedMods[0])?.priority}</span>
                <span>Path: {selectedMods[0]}</span>
              </div>
            </div>
          ) : (
            <div className="p-3">
              <h2>Multiple Mods Selected ({selectedMods.length})</h2>
              <p>Bulk operations available:</p>
              <div className="mod-actions">
                <Button
                  variant="success"
                  onClick={handleEnableMods}
                  title="Enable selected mods"
                >
                  <i className="material-icons">visibility</i>
                  <span>Enable All</span>
                </Button>
                <Button
                  variant="warning"
                  onClick={handleDisableMods}
                  title="Disable selected mods"
                >
                  <i className="material-icons">visibility_off</i>
                  <span>Disable All</span>
                </Button>
                <Button
                  variant="info"
                  onClick={exploreModFolders}
                  title="Open mod folders"
                >
                  <i className="material-icons">folder_open</i>
                  <span>Explore</span>
                </Button>
                <Button
                  variant="secondary"
                  onClick={reprocessMods}
                  title="Reprocess mods"
                >
                  <i className="material-icons">refresh</i>
                  <span>Reprocess</span>
                </Button>
                <Button
                  variant="danger"
                  onClick={handleUninstallMods}
                  title="Uninstall selected mods"
                >
                  <i className="material-icons">delete</i>
                  <span>Uninstall</span>
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Floating Action Button */}
      <button
        className="fab"
        title="Install (Ctrl+I)"
        onClick={() => setShowInstallModal(true)}
      >
        <i className="material-icons">add</i>
      </button>

      {/* Mod Installation Modal */}
      <Modal show={showInstallModal} onHide={() => setShowInstallModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Install Mod</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Select Mod Files</Form.Label>
              <div className="d-grid gap-2">
                <Button variant="outline-primary" onClick={handleSelectModFiles}>
                  Browse for Mod Files (.bnp, .zip, .7z, .rar)
                </Button>
              </div>
              {installFiles.length > 0 && (
                <div className="mt-2">
                  <strong>Selected Files:</strong>
                  <ul className="list-group mt-1">
                    {installFiles.map((file, index) => (
                      <li key={index} className="list-group-item">
                        {file.split('/').pop() || file.split('\\').pop()}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Form.Group>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowInstallModal(false)}>
            Cancel
          </Button>
          <Button 
            variant="primary" 
            onClick={handleInstallSelectedMods}
            disabled={installFiles.length === 0}
          >
            Install {installFiles.length > 0 ? `(${installFiles.length} files)` : ''}
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}

export default ModsTab;