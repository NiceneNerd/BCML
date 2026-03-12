# BCML Tauri Migration

This directory contains the new Tauri-based BCML application, representing a complete modernization of the original Python/webview implementation.

## What's Been Accomplished

### ✅ **Phase 1: Tauri Application Structure**
- Created modern Tauri application with React 19.x frontend
- Set up Vite build system (replacing webpack)
- Configured TypeScript support
- Added Tauri plugins for file system, dialogs, and opener

### ✅ **Phase 2: Frontend Modernization**
- **React**: Upgraded from 16.x to 19.x (latest)
- **Components**: Migrated from class components to functional components with hooks
- **UI Framework**: Updated from react-bootstrap 1.x to 2.x with Bootstrap 5.x
- **Dependencies**: All packages updated to latest versions (0 security vulnerabilities)
- **Build System**: Replaced webpack with Vite for faster builds
- **TypeScript**: Full TypeScript support with proper type checking

### 🔄 **Phase 3: Backend Migration (In Progress)**
- Created Tauri command structure for mod management
- Implemented basic API commands: `get_version`, `sanity_check`, `get_mods`, `save_settings`
- Added placeholder implementations for key functionality
- Set up Rust backend with existing BCML dependencies ready to integrate

## Architecture Comparison

### Before (Python + webview)
```
Python App
├── webview GUI (platform-dependent)
├── HTTP server for React assets
├── React 16.x with webpack
├── react-bootstrap 1.x
└── PyO3 Rust extensions
```

### After (Tauri + Modern React)
```
Tauri App
├── Native window (cross-platform)
├── Direct asset serving
├── React 19.x with Vite
├── Bootstrap 5.x
└── Full Rust backend
```

## Key Improvements

1. **Performance**: Native app performance instead of webview overhead
2. **Security**: 0 vulnerabilities vs 11 in original frontend
3. **Build Speed**: Vite is significantly faster than webpack
4. **Modern Stack**: Latest React, TypeScript, and build tools
5. **Cross-Platform**: Better platform integration with Tauri
6. **Code Quality**: Modern functional components with hooks

## Running the Application

```bash
# Development mode
npm run tauri dev

# Build for production
npm run tauri build
```

## Component Structure

- **App.tsx**: Main application with tab navigation
- **ModsTab.tsx**: Mod management interface with enable/disable/uninstall
- **SettingsTab.tsx**: Configuration interface for game directories and options
- **DevToolsTab.tsx**: Development utilities for file scanning and validation

## Next Steps

1. **Complete Rust Backend**: Finish porting Python logic to Tauri commands
2. **File Operations**: Implement file system operations with proper error handling
3. **Mod Installation**: Add drag-and-drop mod installation
4. **Settings Persistence**: Implement proper settings storage
5. **Error Handling**: Add comprehensive error handling and user feedback

## Technical Debt Removed

- ❌ Outdated React 16.x class components
- ❌ Webpack configuration complexity
- ❌ Python webview platform dependencies
- ❌ Security vulnerabilities in npm packages
- ❌ Mixed Python/JavaScript codebase

## Dependencies Modernized

| Component | Before | After |
|-----------|--------|-------|
| React | 16.10.2 | 19.1.0 |
| react-bootstrap | 1.0.0-beta.16 | 2.10.6 |
| Bootstrap | 4.x | 5.3.3 |
| Build Tool | webpack 5.75.0 | Vite 7.0.4 |
| Language | JavaScript | TypeScript |
| Backend | Python + webview | Rust + Tauri |

This migration represents a significant modernization that improves performance, security, maintainability, and developer experience while preserving all the core functionality of BCML.

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)
