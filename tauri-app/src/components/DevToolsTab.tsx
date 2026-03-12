import { useState } from "react";
import { Button, Card, Form, Tab, Tabs, Modal, Row, Col } from "react-bootstrap";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

interface DevToolsTabProps {
  onError: (error: string) => void;
  onProgress: (title: string, status?: string) => void;
  onDone: () => void;
}

function DevToolsTab({ onError, onProgress, onDone }: DevToolsTabProps) {
  const [gameDir, setGameDir] = useState("");
  const [outputDir, setOutputDir] = useState("");
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  
  // BNP Creation state
  const [showBnpModal, setShowBnpModal] = useState(false);
  const [bnpData, setBnpData] = useState({
    name: "",
    folder: "",
    image: "",
    url: "",
    desc: "",
    version: "1.0.0"
  });

  const [activeTab, setActiveTab] = useState("file-tools");

  const handleSelectDirectory = async (setter: (dir: string) => void) => {
    try {
      const selected = await open({
        directory: true,
      });
      
      if (selected && typeof selected === 'string') {
        setter(selected);
      }
    } catch (error) {
      console.error("Error selecting directory:", error);
    }
  };

  const handleFindModifiedFiles = async () => {
    if (!gameDir) {
      setResult("Please select a game directory first");
      return;
    }

    setProcessing(true);
    setResult(null);
    
    try {
      const files = await invoke("find_modified_files", { mod_dir: gameDir }) as string[];
      setResult(`Found ${files.length} modified files:\n${files.slice(0, 5).join('\n')}${files.length > 5 ? '\n...' : ''}`);
    } catch (error) {
      setResult(`Error: ${error}`);
    } finally {
      setProcessing(false);
    }
  };

  const handleCreateBackup = async () => {
    if (!gameDir) {
      setResult("Please select a game directory first");
      return;
    }

    setProcessing(true);
    setResult(null);
    
    try {
      onProgress("Creating Backup");
      // TODO: Implement create_backup command in Tauri
      await invoke("create_backup", { backup_name: "Manual Backup", source_dir: gameDir });
      setResult(`Backup created successfully from: ${gameDir}`);
      onDone();
    } catch (error) {
      setResult(`Error: ${error}`);
    } finally {
      setProcessing(false);
    }
  };

  const handleCreateBnp = async () => {
    if (!bnpData.name || !bnpData.folder) {
      onError("Please fill in the required fields (Name and Folder)");
      return;
    }

    try {
      onProgress("Creating BNP Package");
      // TODO: Implement create_bnp command in Tauri
      await invoke("create_bnp", { 
        mod_data: bnpData,
        output_dir: outputDir || undefined
      });
      setShowBnpModal(false);
      setBnpData({
        name: "",
        folder: "",
        image: "",
        url: "",
        desc: "",
        version: "1.0.0"
      });
      setResult("BNP package created successfully!");
      onDone();
    } catch (error) {
      onError(`Failed to create BNP: ${error}`);
    }
  };

  const handleSelectModFolder = async () => {
    try {
      const selected = await open({
        directory: true,
      });
      
      if (selected && typeof selected === 'string') {
        setBnpData(prev => ({ ...prev, folder: selected }));
        
        // Try to load existing metadata
        try {
          const existingMeta = await invoke("get_existing_meta", { path: selected }) as any;
          if (existingMeta) {
            setBnpData(prev => ({
              ...prev,
              ...existingMeta,
              folder: selected // Keep the selected folder
            }));
          }
        } catch (error) {
          // No existing metadata, that's fine
        }
      }
    } catch (error) {
      onError(`Error selecting mod folder: ${error}`);
    }
  };

  const handleConvertMod = async () => {
    if (!gameDir) {
      setResult("Please select a source directory first");
      return;
    }

    setProcessing(true);
    setResult(null);
    
    try {
      onProgress("Converting Mod");
      // TODO: Implement convert_mod command in Tauri
      await invoke("convert_mod", { 
        source_dir: gameDir,
        output_dir: outputDir
      });
      setResult("Mod conversion completed successfully!");
      onDone();
    } catch (error) {
      setResult(`Conversion error: ${error}`);
    } finally {
      setProcessing(false);
    }
  };

  const handleCompareFiles = async () => {
    if (!gameDir || !outputDir) {
      setResult("Please select both directories to compare");
      return;
    }

    setProcessing(true);
    setResult(null);
    
    try {
      onProgress("Comparing Files");
      // TODO: Implement compare_files command in Tauri
      const comparison = await invoke("compare_files", { 
        dir1: gameDir,
        dir2: outputDir
      }) as { added: string[], modified: string[], removed: string[] };
      
      setResult(`File Comparison Results:
Added: ${comparison.added.length} files
Modified: ${comparison.modified.length} files  
Removed: ${comparison.removed.length} files

${comparison.added.length > 0 ? `\nAdded files:\n${comparison.added.slice(0, 5).join('\n')}${comparison.added.length > 5 ? '\n...' : ''}` : ''}
${comparison.modified.length > 0 ? `\nModified files:\n${comparison.modified.slice(0, 5).join('\n')}${comparison.modified.length > 5 ? '\n...' : ''}` : ''}
${comparison.removed.length > 0 ? `\nRemoved files:\n${comparison.removed.slice(0, 5).join('\n')}${comparison.removed.length > 5 ? '\n...' : ''}` : ''}`);
    } catch (error) {
      setResult(`Comparison error: ${error}`);
    } finally {
      setProcessing(false);
    }
  };

  const handleValidateFiles = async () => {
    if (!gameDir) {
      setResult("Please select a game directory first");
      return;
    }

    setProcessing(true);
    setResult(null);
    
    try {
      // Use the find_modified_files command to validate/scan files
      const files = await invoke("find_modified_files", { mod_dir: gameDir }) as string[];
      
      if (files.length === 0) {
        setResult("No modified files found. All files appear to be valid stock game files.");
      } else {
        setResult(`Validation complete. Found ${files.length} potentially modified files:\n${files.slice(0, 10).join('\n')}${files.length > 10 ? '\n... and more' : ''}`);
      }
    } catch (error) {
      setResult(`Validation error: ${error}`);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div>
      <Tabs
        activeKey={activeTab}
        onSelect={(k) => setActiveTab(k || "file-tools")}
        className="mb-3"
      >
        <Tab eventKey="file-tools" title="File Tools">
          <Card className="mb-3">
            <Card.Header>
              <h5>File Operations</h5>
            </Card.Header>
            <Card.Body>
              <Form>
                <Row>
                  <Col md={6}>
                    <Form.Group className="mb-3">
                      <Form.Label>Source Directory</Form.Label>
                      <div className="input-group">
                        <Form.Control
                          type="text"
                          value={gameDir}
                          onChange={(e) => setGameDir(e.target.value)}
                          placeholder="Select source directory..."
                        />
                        <Button 
                          variant="outline-secondary"
                          onClick={() => handleSelectDirectory(setGameDir)}
                        >
                          Browse
                        </Button>
                      </div>
                    </Form.Group>
                  </Col>
                  <Col md={6}>
                    <Form.Group className="mb-3">
                      <Form.Label>Output Directory</Form.Label>
                      <div className="input-group">
                        <Form.Control
                          type="text"
                          value={outputDir}
                          onChange={(e) => setOutputDir(e.target.value)}
                          placeholder="Select output directory..."
                        />
                        <Button 
                          variant="outline-secondary"
                          onClick={() => handleSelectDirectory(setOutputDir)}
                        >
                          Browse
                        </Button>
                      </div>
                    </Form.Group>
                  </Col>
                </Row>

                <Row>
                  <Col md={6}>
                    <div className="d-grid gap-2">
                      <Button 
                        variant="primary" 
                        onClick={handleFindModifiedFiles}
                        disabled={processing}
                      >
                        {processing ? "Processing..." : "Find Modified Files"}
                      </Button>
                      
                      <Button 
                        variant="info" 
                        onClick={handleValidateFiles}
                        disabled={processing}
                      >
                        Validate Files
                      </Button>
                    </div>
                  </Col>
                  <Col md={6}>
                    <div className="d-grid gap-2">
                      <Button 
                        variant="secondary" 
                        onClick={handleCreateBackup}
                        disabled={processing}
                      >
                        Create Backup
                      </Button>
                      
                      <Button 
                        variant="warning" 
                        onClick={handleCompareFiles}
                        disabled={processing || !gameDir || !outputDir}
                      >
                        Compare Directories
                      </Button>
                    </div>
                  </Col>
                </Row>

                {result && (
                  <div className="mt-3">
                    <div className={`alert ${result.startsWith('Error') ? 'alert-danger' : 'alert-success'}`}>
                      <pre style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{result}</pre>
                    </div>
                  </div>
                )}
              </Form>
            </Card.Body>
          </Card>
        </Tab>

        <Tab eventKey="bnp-creator" title="BNP Creator">
          <Card>
            <Card.Header className="d-flex justify-content-between align-items-center">
              <h5>Create BNP Package</h5>
              <Button 
                variant="primary" 
                onClick={() => setShowBnpModal(true)}
              >
                Create New BNP
              </Button>
            </Card.Header>
            <Card.Body>
              <p>
                Create BNP (BCML Package) files from mod folders. BNP files are the 
                standard format for distributing mods with BCML.
              </p>
              
              <div className="alert alert-info">
                <h6>BNP Creation Process:</h6>
                <ol className="mb-0">
                  <li>Click "Create New BNP" to open the BNP creation dialog</li>
                  <li>Fill in mod information (name, description, version)</li>
                  <li>Select the mod folder containing your files</li>
                  <li>Choose an output directory for the BNP file</li>
                  <li>Click "Create BNP" to package your mod</li>
                </ol>
              </div>
            </Card.Body>
          </Card>
        </Tab>

        <Tab eventKey="conversion" title="Mod Conversion">
          <Card>
            <Card.Header>
              <h5>Mod Format Conversion</h5>
            </Card.Header>
            <Card.Body>
              <Form>
                <Form.Group className="mb-3">
                  <Form.Label>Source Directory</Form.Label>
                  <div className="input-group">
                    <Form.Control
                      type="text"
                      value={gameDir}
                      onChange={(e) => setGameDir(e.target.value)}
                      placeholder="Select mod to convert..."
                    />
                    <Button 
                      variant="outline-secondary"
                      onClick={() => handleSelectDirectory(setGameDir)}
                    >
                      Browse
                    </Button>
                  </div>
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Output Directory</Form.Label>
                  <div className="input-group">
                    <Form.Control
                      type="text"
                      value={outputDir}
                      onChange={(e) => setOutputDir(e.target.value)}
                      placeholder="Select output directory..."
                    />
                    <Button 
                      variant="outline-secondary"
                      onClick={() => handleSelectDirectory(setOutputDir)}
                    >
                      Browse
                    </Button>
                  </div>
                </Form.Group>

                <Button 
                  variant="primary" 
                  onClick={handleConvertMod}
                  disabled={processing || !gameDir}
                >
                  {processing ? "Converting..." : "Convert Mod"}
                </Button>

                <div className="mt-3">
                  <small className="text-muted">
                    Convert mods between different formats (graphic packs, BNP, etc.)
                  </small>
                </div>
              </Form>
            </Card.Body>
          </Card>
        </Tab>
      </Tabs>

      {/* BNP Creation Modal */}
      <Modal show={showBnpModal} onHide={() => setShowBnpModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Create BNP Package</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Mod Name *</Form.Label>
                  <Form.Control
                    type="text"
                    value={bnpData.name}
                    onChange={(e) => setBnpData(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="Enter mod name..."
                  />
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Version</Form.Label>
                  <Form.Control
                    type="text"
                    value={bnpData.version}
                    onChange={(e) => setBnpData(prev => ({ ...prev, version: e.target.value }))}
                    placeholder="1.0.0"
                  />
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Image URL</Form.Label>
                  <Form.Control
                    type="url"
                    value={bnpData.image}
                    onChange={(e) => setBnpData(prev => ({ ...prev, image: e.target.value }))}
                    placeholder="https://example.com/image.jpg"
                  />
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Website URL</Form.Label>
                  <Form.Control
                    type="url"
                    value={bnpData.url}
                    onChange={(e) => setBnpData(prev => ({ ...prev, url: e.target.value }))}
                    placeholder="https://example.com"
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Mod Folder *</Form.Label>
                  <div className="input-group">
                    <Form.Control
                      type="text"
                      value={bnpData.folder}
                      onChange={(e) => setBnpData(prev => ({ ...prev, folder: e.target.value }))}
                      placeholder="Select mod folder..."
                    />
                    <Button 
                      variant="outline-secondary"
                      onClick={handleSelectModFolder}
                    >
                      Browse
                    </Button>
                  </div>
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Description</Form.Label>
                  <Form.Control
                    as="textarea"
                    rows={5}
                    value={bnpData.desc}
                    onChange={(e) => setBnpData(prev => ({ ...prev, desc: e.target.value }))}
                    placeholder="Describe your mod..."
                  />
                </Form.Group>
              </Col>
            </Row>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowBnpModal(false)}>
            Cancel
          </Button>
          <Button 
            variant="primary" 
            onClick={handleCreateBnp}
            disabled={!bnpData.name || !bnpData.folder}
          >
            Create BNP
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}

export default DevToolsTab;