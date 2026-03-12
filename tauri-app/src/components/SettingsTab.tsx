import { useState, useEffect } from "react";
import { Button, Card, Col, Form, Row } from "react-bootstrap";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

interface Settings {
  game_dir: string;
  game_dir_nx: string;
  update_dir: string;
  dlc_dir: string;
  dlc_dir_nx: string;
  cemu_dir: string;
  store_dir: string;
  export_dir: string;
  export_dir_nx: string;
  wiiu: boolean;
  lang: string;
  no_cemu: boolean;
  no_hardlinks: boolean;
  force_7z: boolean;
  suppress_update: boolean;
  load_reverse: boolean;
  nsfw: boolean;
  changelog: boolean;
  strip_gfx: boolean;
  auto_gb: boolean;
  show_gb: boolean;
  site_meta: string;
  no_guess: boolean;
}

interface SettingsTabProps {
  onError: (error: string) => void;
  onProgress?: (title: string, status?: string) => void;
  onDone?: () => void;
  onSettingsValid?: (valid: boolean) => void;
  onSaveSettings?: (settings: Settings) => void;
  isFirstRun?: boolean;
  saving?: boolean;
}

const LANGUAGES = [
  "USen", "EUen", "USfr", "USes", "EUde", "EUes", "EUfr", "EUit", "EUnl", "EUru", "CNzh", "JPja", "KRko", "TWzh"
];

function SettingsTab({ 
  onError, 
  onProgress, 
  onDone, 
  onSettingsValid, 
  onSaveSettings, 
  isFirstRun = false, 
  saving: externalSaving = false 
}: SettingsTabProps) {
  const [settings, setSettings] = useState<Settings>({
    game_dir: "",
    game_dir_nx: "",
    update_dir: "",
    dlc_dir: "",
    dlc_dir_nx: "",
    cemu_dir: "",
    store_dir: "",
    export_dir: "",
    export_dir_nx: "",
    wiiu: true,
    lang: "USen",
    no_cemu: false,
    no_hardlinks: false,
    force_7z: false,
    suppress_update: false,
    load_reverse: false,
    nsfw: false,
    changelog: true,
    strip_gfx: false,
    auto_gb: true,
    show_gb: true,
    site_meta: "",
    no_guess: false,
  });
  const [isDirty, setIsDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  const [isValid, setIsValid] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  useEffect(() => {
    validateSettings();
    // Notify parent component about validation status for first-run wizard
    if (onSettingsValid) {
      onSettingsValid(isValid);
    }
  }, [settings, isValid, onSettingsValid]);

  const loadSettings = async () => {
    try {
      // Check if we're running in Tauri context
      if (typeof window !== 'undefined' && (window as any).__TAURI__) {
        const loadedSettings = await invoke("get_settings") as Settings;
        setSettings(loadedSettings);
      } else {
        // Mock settings for browser development
        setSettings({
          game_dir: "/path/to/game",
          game_dir_nx: "/path/to/game_nx",
          update_dir: "/path/to/update",
          dlc_dir: "/path/to/dlc",
          dlc_dir_nx: "/path/to/dlc_nx",
          cemu_dir: "/path/to/cemu",
          store_dir: "/path/to/store",
          export_dir: "/path/to/export",
          export_dir_nx: "/path/to/export_nx",
          wiiu: true,
          lang: "USen",
          no_cemu: false,
          no_hardlinks: false,
          force_7z: false,
          suppress_update: false,
          load_reverse: false,
          nsfw: false,
          changelog: true,
          strip_gfx: false,
          auto_gb: false,
          show_gb: true,
          site_meta: "",
          no_guess: false,
        });
      }
    } catch (error) {
      console.error("Failed to load settings:", error);
      onError(`Failed to load settings: ${error}`);
    }
  };

  const validateSettings = async () => {
    try {
      // Basic validation - check required fields
      const requiredFields = [
        settings.wiiu ? settings.game_dir : settings.game_dir_nx,
        settings.store_dir,
        settings.lang
      ];
      
      if (settings.wiiu && !settings.no_cemu) {
        requiredFields.push(settings.cemu_dir);
      }

      const allFieldsFilled = requiredFields.every(field => field && field.trim() !== "");
      
      // TODO: Add directory existence validation via Tauri commands
      setIsValid(allFieldsFilled);
    } catch (error) {
      setIsValid(false);
    }
  };

  const handleSettingChange = (key: keyof Settings, value: any) => {
    setSettings(prev => ({ ...prev, [key]: value }));
    setIsDirty(true);
    setMessage(null);
  };

  const handleDirectorySelect = async (settingKey: keyof Settings) => {
    try {
      const selected = await open({
        directory: true,
      });
      
      if (selected && typeof selected === 'string') {
        handleSettingChange(settingKey, selected);
      }
    } catch (error) {
      console.error("Error selecting directory:", error);
      onError(`Failed to select directory: ${error}`);
    }
  };

  const handleSave = async () => {
    if (!isValid) {
      onError("Your settings are not valid and cannot be saved. Check that all required fields are completed.");
      return;
    }

    if (isFirstRun && onSaveSettings) {
      // In first-run mode, let the wizard handle saving
      onSaveSettings(settings);
    } else {
      // Normal save mode
      setSaving(true);
      try {
        if (onProgress) onProgress("Saving Settings");
        await invoke("save_settings", { settings });
        setIsDirty(false);
        setMessage({ type: 'success', text: 'Settings saved successfully!' });
        if (onDone) onDone();
      } catch (error) {
        onError(`Failed to save settings: ${error}`);
      } finally {
        setSaving(false);
      }
    }
  };

  const handleReset = () => {
    const resetSettings: Settings = {
      game_dir: "",
      game_dir_nx: "",
      update_dir: "",
      dlc_dir: "",
      dlc_dir_nx: "",
      cemu_dir: "",
      store_dir: "",
      export_dir: "",
      export_dir_nx: "",
      wiiu: true,
      lang: "USen",
      no_cemu: false,
      no_hardlinks: false,
      force_7z: false,
      suppress_update: false,
      load_reverse: false,
      nsfw: false,
      changelog: true,
      strip_gfx: false,
      auto_gb: true,
      show_gb: true,
      site_meta: "",
      no_guess: false,
    };
    setSettings(resetSettings);
    setIsDirty(true);
    setMessage(null);
  };

  return (
    <div>
      <Card>
        <Card.Header className="d-flex justify-content-between align-items-center">
          <h5>BCML Settings</h5>
          <div>
            <Button 
              variant="outline-secondary" 
              className="me-2"
              onClick={handleReset}
            >
              Reset to Defaults
            </Button>
            <Button 
              variant="primary" 
              onClick={handleSave}
              disabled={!isDirty || (saving || externalSaving) || !isValid}
            >
              {(saving || externalSaving) ? "Saving..." : "Save Settings"}
            </Button>
          </div>
        </Card.Header>
        <Card.Body>
          {message && (
            <div className={`alert alert-${message.type === 'success' ? 'success' : 'danger'} mb-3`}>
              {message.text}
            </div>
          )}

          <Form>
            <Row>
              <Col md={6}>
                <h6>Platform Settings</h6>
                <Form.Group className="mb-3">
                  <Form.Check
                    type="radio"
                    id="platform-wiiu"
                    label="Wii U"
                    checked={settings.wiiu}
                    onChange={(e) => handleSettingChange('wiiu', e.target.checked)}
                  />
                  <Form.Check
                    type="radio"
                    id="platform-switch"
                    label="Nintendo Switch"
                    checked={!settings.wiiu}
                    onChange={(e) => handleSettingChange('wiiu', !e.target.checked)}
                  />
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Language *</Form.Label>
                  <Form.Select
                    value={settings.lang}
                    onChange={(e) => handleSettingChange('lang', e.target.value)}
                    className={settings.lang ? "is-valid" : "is-invalid"}
                  >
                    {LANGUAGES.map(lang => (
                      <option key={lang} value={lang}>{lang}</option>
                    ))}
                  </Form.Select>
                </Form.Group>

                {settings.wiiu && (
                  <Form.Group className="mb-3">
                    <Form.Label>Cemu Directory {!settings.no_cemu && "*"}</Form.Label>
                    <div className="input-group">
                      <Form.Control
                        type="text"
                        value={settings.cemu_dir}
                        onChange={(e) => handleSettingChange('cemu_dir', e.target.value)}
                        placeholder="Path to Cemu installation..."
                        className={settings.no_cemu || settings.cemu_dir ? "is-valid" : "is-invalid"}
                      />
                      <Button 
                        variant="outline-secondary"
                        onClick={() => handleDirectorySelect('cemu_dir')}
                      >
                        Browse
                      </Button>
                    </div>
                    <Form.Check
                      type="checkbox"
                      id="no-cemu"
                      label="I don't use Cemu"
                      checked={settings.no_cemu}
                      onChange={(e) => handleSettingChange('no_cemu', e.target.checked)}
                      className="mt-1"
                    />
                  </Form.Group>
                )}

                <Form.Group className="mb-3">
                  <Form.Label>Game Directory *</Form.Label>
                  <div className="input-group">
                    <Form.Control
                      type="text"
                      value={settings.wiiu ? settings.game_dir : settings.game_dir_nx}
                      onChange={(e) => handleSettingChange(
                        settings.wiiu ? 'game_dir' : 'game_dir_nx', 
                        e.target.value
                      )}
                      placeholder="Path to game files..."
                      className={(settings.wiiu ? settings.game_dir : settings.game_dir_nx) ? "is-valid" : "is-invalid"}
                    />
                    <Button 
                      variant="outline-secondary"
                      onClick={() => handleDirectorySelect(settings.wiiu ? 'game_dir' : 'game_dir_nx')}
                    >
                      Browse
                    </Button>
                  </div>
                </Form.Group>

                {settings.wiiu && (
                  <Form.Group className="mb-3">
                    <Form.Label>Update Directory</Form.Label>
                    <div className="input-group">
                      <Form.Control
                        type="text"
                        value={settings.update_dir}
                        onChange={(e) => handleSettingChange('update_dir', e.target.value)}
                        placeholder="Path to update files..."
                      />
                      <Button 
                        variant="outline-secondary"
                        onClick={() => handleDirectorySelect('update_dir')}
                      >
                        Browse
                      </Button>
                    </div>
                  </Form.Group>
                )}

                <Form.Group className="mb-3">
                  <Form.Label>DLC Directory</Form.Label>
                  <div className="input-group">
                    <Form.Control
                      type="text"
                      value={settings.wiiu ? settings.dlc_dir : settings.dlc_dir_nx}
                      onChange={(e) => handleSettingChange(
                        settings.wiiu ? 'dlc_dir' : 'dlc_dir_nx', 
                        e.target.value
                      )}
                      placeholder="Path to DLC files..."
                    />
                    <Button 
                      variant="outline-secondary"
                      onClick={() => handleDirectorySelect(settings.wiiu ? 'dlc_dir' : 'dlc_dir_nx')}
                    >
                      Browse
                    </Button>
                  </div>
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Mod Storage Directory *</Form.Label>
                  <div className="input-group">
                    <Form.Control
                      type="text"
                      value={settings.store_dir}
                      onChange={(e) => handleSettingChange('store_dir', e.target.value)}
                      placeholder="Path to store mods..."
                      className={settings.store_dir ? "is-valid" : "is-invalid"}
                    />
                    <Button 
                      variant="outline-secondary"
                      onClick={() => handleDirectorySelect('store_dir')}
                    >
                      Browse
                    </Button>
                  </div>
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Export Directory</Form.Label>
                  <div className="input-group">
                    <Form.Control
                      type="text"
                      value={settings.wiiu ? settings.export_dir : settings.export_dir_nx}
                      onChange={(e) => handleSettingChange(
                        settings.wiiu ? 'export_dir' : 'export_dir_nx', 
                        e.target.value
                      )}
                      placeholder="Path for mod exports..."
                    />
                    <Button 
                      variant="outline-secondary"
                      onClick={() => handleDirectorySelect(settings.wiiu ? 'export_dir' : 'export_dir_nx')}
                    >
                      Browse
                    </Button>
                  </div>
                </Form.Group>
              </Col>

              <Col md={6}>
                <h6>Advanced Options</h6>
                
                <Form.Group className="mb-3">
                  <Form.Label>Site Meta File</Form.Label>
                  <Form.Control
                    type="text"
                    value={settings.site_meta}
                    onChange={(e) => handleSettingChange('site_meta', e.target.value)}
                    placeholder="Optional site meta file path..."
                  />
                </Form.Group>

                <div className="mb-3">
                  <h6>Mod Loading Options</h6>
                  <Form.Check
                    type="checkbox"
                    id="load-reverse"
                    label="Load mods in reverse order"
                    checked={settings.load_reverse}
                    onChange={(e) => handleSettingChange('load_reverse', e.target.checked)}
                  />
                  <Form.Check
                    type="checkbox"
                    id="no-guess"
                    label="Don't guess mod metadata"
                    checked={settings.no_guess}
                    onChange={(e) => handleSettingChange('no_guess', e.target.checked)}
                  />
                </div>

                <div className="mb-3">
                  <h6>File Options</h6>
                  <Form.Check
                    type="checkbox"
                    id="no-hardlinks"
                    label="Don't use hardlinks"
                    checked={settings.no_hardlinks}
                    onChange={(e) => handleSettingChange('no_hardlinks', e.target.checked)}
                  />
                  <Form.Check
                    type="checkbox"
                    id="force-7z"
                    label="Force 7z compression"
                    checked={settings.force_7z}
                    onChange={(e) => handleSettingChange('force_7z', e.target.checked)}
                  />
                  <Form.Check
                    type="checkbox"
                    id="strip-gfx"
                    label="Strip graphics pack files"
                    checked={settings.strip_gfx}
                    onChange={(e) => handleSettingChange('strip_gfx', e.target.checked)}
                  />
                </div>

                <div className="mb-3">
                  <h6>UI Options</h6>
                  <Form.Check
                    type="checkbox"
                    id="nsfw"
                    label="Allow NSFW content"
                    checked={settings.nsfw}
                    onChange={(e) => handleSettingChange('nsfw', e.target.checked)}
                  />
                  <Form.Check
                    type="checkbox"
                    id="changelog"
                    label="Show changelog on update"
                    checked={settings.changelog}
                    onChange={(e) => handleSettingChange('changelog', e.target.checked)}
                  />
                  <Form.Check
                    type="checkbox"
                    id="suppress-update"
                    label="Suppress update notifications"
                    checked={settings.suppress_update}
                    onChange={(e) => handleSettingChange('suppress_update', e.target.checked)}
                  />
                  <Form.Check
                    type="checkbox"
                    id="auto-gb"
                    label="Auto graphic pack conversion"
                    checked={settings.auto_gb}
                    onChange={(e) => handleSettingChange('auto_gb', e.target.checked)}
                  />
                  <Form.Check
                    type="checkbox"
                    id="show-gb"
                    label="Show graphic pack options"
                    checked={settings.show_gb}
                    onChange={(e) => handleSettingChange('show_gb', e.target.checked)}
                  />
                </div>

                <div className="card mt-3">
                  <div className="card-body">
                    <h6 className="card-title">Migration Status</h6>
                    <ul className="list-unstyled mb-0">
                      <li>✅ Modern React 19.x frontend</li>
                      <li>✅ Tauri native backend</li>
                      <li>✅ Complete settings interface</li>
                      <li>✅ Directory browsing</li>
                      <li>✅ Settings validation</li>
                      <li>✅ All configuration options</li>
                    </ul>
                  </div>
                </div>
              </Col>
            </Row>
          </Form>
        </Card.Body>
      </Card>
    </div>
  );
}

export default SettingsTab;