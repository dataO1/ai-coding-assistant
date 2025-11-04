# UI/FRONTEND - COMPREHENSIVE ARCHITECTURE & IMPLEMENTATION GUIDE

**Status**: Complete Architectural Specification  
**Last Updated**: November 4, 2025  
**Version**: 2.0  
**Audience**: Frontend developers (Rust/Iced), no prior project knowledge assumed

---

## TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Architectural Overview](#architectural-overview)
3. [Component Design](#component-design)
4. [State Management](#state-management)
5. [User Flow & Interactions](#user-flow--interactions)
6. [Data Models](#data-models)
7. [Configuration Management](#configuration-management)
8. [API Communication](#api-communication)
9. [Deployment & Build](#deployment--build)
10. [Implementation Roadmap](#implementation-roadmap)
11. [Development Guidelines](#development-guidelines)

---

## EXECUTIVE SUMMARY

### What This System Does

The UI is a **Rust GPU-accelerated desktop application** (using Iced + Wgpu) that:

1. **Manages workspace selection** (like VS Code "Open Folder")
2. **Loads and displays configs** (agents, workflows, retrieval strategies)
3. **Submits workflow requests** to backend with complete pipeline definition
4. **Streams real-time updates** (status, progress, completion)
5. **Displays hierarchical diff view** (commits → files → hunks → code on-demand)
6. **Handles user feedback** (accept/reject/modify changes)

**Key Point**: UI sends complete workflow config to backend per request. GUI is not just a renderer—it's a configuration engine that the user controls.

### Technology Stack

| Component | Technology | Reasoning |
|-----------|-----------|-----------|
| Framework | Iced | Rust, GPU-accelerated, immediate-mode GUI |
| Rendering | Wgpu | Vulkan/Metal/DX12, modern GPU rendering |
| Async Runtime | Tokio | Async network requests, UI responsiveness |
| State Management | Elm architecture | Predictable state changes, debugging |
| Configuration | YAML parsing | Same format as backend, versionable |
| HTTP Client | Reqwest | Async, Tokio-integrated |
| WebSocket | Tokio-tungstenite | Real-time streaming updates |
| Serialization | Serde | JSON/YAML serialization |
| Logging | tracing | Structured logging, spans |

---

## ARCHITECTURAL OVERVIEW

### Three-Component Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ COMPONENT 1: WORKSPACE MANAGEMENT                             │
│ - Folder browser (select workspace like VS Code)              │
│ - .agentic-ide/config.yaml loader                            │
│ - Workspace context builder                                   │
│ - Recent projects list                                        │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ COMPONENT 2: CONFIGURATION & WORKFLOW INTERFACE              │
│ - Load config files (agents.yaml, workflows.yaml, etc)       │
│ - Workflow selector dropdown                                  │
│ - User query input                                            │
│ - Execute/Submit button                                       │
│ - Status indicator                                            │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ COMPONENT 3: HIERARCHICAL DIFF VIEW & REVIEW                 │
│ - Level 1: Commits summary (metadata, no code)               │
│ - Level 2: Files per commit                                   │
│ - Level 3: Hunks (changed sections)                          │
│ - Level 4: Code on-demand (lazy load via API call)           │
│ - Actions: Accept/Reject/Feedback per level                  │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ COMPONENT 4: REAL-TIME STREAMING & COMMUNICATION             │
│ - WebSocket/SSE connection to backend                        │
│ - Status update processing                                    │
│ - Workflow completion handling                                │
│ - Error display                                               │
└──────────────────────────────────────────────────────────────┘
```

### Request Lifecycle

```
1. User selects workspace (GUI)
   └─ Load .agentic-ide/config.yaml

2. User selects workflow
   └─ Display available workflows from workflows.yaml

3. User enters query & clicks Submit
   └─ Build complete request payload

4. GUI submits POST /api/workflow/submit
   ├─ Payload includes complete configs
   ├─ Backend returns execution_id
   ├─ GUI receives streaming URL
   └─ GUI opens WebSocket to stream endpoint

5. GUI displays status updates in real-time
   ├─ Footer: "Generating code...", progress
   └─ Continue streaming

6. Backend sends workflow_complete
   ├─ GUI receives commit metadata
   ├─ GUI displays hierarchical diff view
   └─ User can interact (zoom, accept, reject)

7. User provides feedback
   └─ GUI restart workflow OR apply changes

8. GUI applies commits to workspace
   └─ Show success message
```

---

## COMPONENT DESIGN

### Component 1: Workspace Management

**Responsibility**: File browser, project selection, context building

**Implementation**:

```rust
// src/components/workspace_manager.rs

pub struct WorkspaceManager {
    current_workspace: Option<WorkspaceContext>,
    recent_workspaces: Vec<WorkspaceInfo>,
    workspace_config: Option<WorkspaceConfig>,
}

impl WorkspaceManager {
    pub fn open_workspace_dialog(&self) -> Command<Message> {
        // Native file browser to select directory
        // Set current_workspace
        Command::perform(
            select_directory(),
            |path| Message::WorkspaceSelected(path)
        )
    }
    
    pub fn load_workspace_config(&self, path: &Path) -> Result<WorkspaceConfig> {
        let config_path = path.join(".agentic-ide/config.yaml");
        
        if config_path.exists() {
            let content = std::fs::read_to_string(&config_path)?;
            let config: WorkspaceConfig = serde_yaml::from_str(&content)?;
            Ok(config)
        } else {
            // Return defaults
            Ok(WorkspaceConfig::default())
        }
    }
    
    pub fn build_workspace_context(&self, path: &Path) -> WorkspaceContext {
        WorkspaceContext {
            workspace_id: self.generate_workspace_id(path),
            working_dir: path.to_string_lossy().to_string(),
            language: detect_language(path),
            framework: detect_framework(path),
        }
    }
}

// UI Rendering
pub fn workspace_selector_view(workspace: &WorkspaceManager) -> Element<Message> {
    column![
        text("Select Workspace").size(24),
        row![
            text_input("No workspace selected", &workspace.current_workspace.name),
            button("Browse").on_press(Message::OpenWorkspaceDialog),
        ],
        // Recent workspaces list
        column(
            workspace.recent_workspaces.iter().map(|info| {
                button(text(&info.name))
                    .on_press(Message::WorkspaceSelected(info.path.clone()))
                    .into()
            })
        )
    ].into()
}
```

---

### Component 2: Configuration & Workflow Interface

**Responsibility**: Load configs, manage workflow selection, handle user input

**Implementation**:

```rust
// src/components/workflow_interface.rs

pub struct WorkflowInterface {
    configs: ConfigBundle,  // agents, workflows, retrieval, mcp
    selected_workflow: Option<String>,
    user_query: String,
    is_loading: bool,
    current_execution_id: Option<String>,
}

pub struct ConfigBundle {
    pub agents: HashMap<String, AgentConfig>,
    pub workflows: HashMap<String, WorkflowConfig>,
    pub retrieval: RetrievalConfig,
    pub mcp_integration: McpConfig,
}

impl WorkflowInterface {
    pub fn load_configs(&mut self, workspace_path: &Path) -> Command<Message> {
        // Load from GUI's config/ directory
        Command::perform(
            load_config_files(workspace_path),
            Message::ConfigsLoaded
        )
    }
    
    pub fn on_workflow_submit(&self) -> Command<Message> {
        let request = WorkflowSubmitRequest {
            workflow_id: format!("workflow_{}", uuid::Uuid::new_v4()),
            workflow_type: self.selected_workflow.clone(),
            user_query: self.user_query.clone(),
            
            // Send complete configs to backend
            workflow_config: serialize_config(&self.configs.workflows[self.selected_workflow]),
            agents_config: serialize_configs(&self.configs.agents),
            retrieval_config: serialize_config(&self.configs.retrieval),
            mcp_config: serialize_config(&self.configs.mcp_integration),
            
            workspace_context: WorkspaceContext::current(),
            correlation_id: generate_correlation_id(),
        };
        
        Command::perform(
            submit_workflow(request),
            Message::WorkflowSubmitted
        )
    }
}

// UI Rendering
pub fn workflow_input_view(interface: &WorkflowInterface) -> Element<Message> {
    column![
        text("Workflow Selection").size(20),
        
        pick_list(
            &interface.available_workflows(),
            interface.selected_workflow.clone(),
            Message::WorkflowSelected
        ),
        
        text_input("Enter your request...", &interface.user_query)
            .on_input(Message::QueryInput),
        
        button("Submit")
            .on_press(Message::SubmitWorkflow)
            .padding(10),
        
        if interface.is_loading {
            text("⏳ Submitting...").color(Color::BLUE)
        } else {
            text("")
        }
    ].into()
}
```

---

### Component 3: Hierarchical Diff View

**Responsibility**: Display commits, files, hunks with lazy-loaded code

**Implementation**:

```rust
// src/components/diff_view.rs

pub struct DiffView {
    commits: Vec<CommitMetadata>,
    expanded_commits: HashSet<String>,
    expanded_files: HashSet<String>,
    expanded_hunks: HashSet<String>,
    loaded_diffs: HashMap<String, DiffContent>,  // Cache lazy-loaded diffs
}

impl DiffView {
    pub fn toggle_commit(&mut self, commit_id: String) {
        if self.expanded_commits.contains(&commit_id) {
            self.expanded_commits.remove(&commit_id);
        } else {
            self.expanded_commits.insert(commit_id);
        }
    }
    
    pub fn load_diff(&self, commit_id: String, file_path: String) -> Command<Message> {
        // Lazy load: only when user clicks "Show changes"
        Command::perform(
            fetch_diff(commit_id, file_path),
            Message::DiffLoaded
        )
    }
}

// UI Rendering: Hierarchical structure
pub fn diff_view(view: &DiffView, execution_id: &str) -> Element<Message> {
    let mut content = column![];
    
    for commit in &view.commits {
        // Level 1: Commit Summary
        let commit_header = row![
            if view.expanded_commits.contains(&commit.commit_id) {
                text("▼")
            } else {
                text("▶")
            }
            .on_press(Message::ToggleCommit(commit.commit_id.clone())),
            
            text(&commit.message).bold(),
            text(format!(" ({} files, +{} -{})", 
                commit.files_changed, 
                commit.additions, 
                commit.deletions
            )).color(Color::GRAY),
        ]
        .padding(10)
        .spacing(10);
        
        content = content.push(
            button(commit_header)
                .on_press(Message::ToggleCommit(commit.commit_id.clone()))
        );
        
        // Level 2: Files in commit (if expanded)
        if view.expanded_commits.contains(&commit.commit_id) {
            for file in &commit.files {
                let file_key = format!("{}:{}", commit.commit_id, file.file_path);
                
                let file_row = row![
                    text("    ├─ "),
                    if view.expanded_files.contains(&file_key) {
                        text("▼")
                    } else {
                        text("▶")
                    },
                    text(&file.file_path),
                    match file.change_type {
                        ChangeType::Created => text("✨ Created").color(Color::GREEN),
                        ChangeType::Modified => text("✏️  Modified").color(Color::BLUE),
                        ChangeType::Deleted => text("🗑️  Deleted").color(Color::RED),
                    },
                    text(format!("+{} -{}", file.additions, file.deletions))
                        .color(Color::GRAY)
                        .size(12),
                ]
                .spacing(5)
                .padding(8);
                
                content = content.push(
                    button(file_row)
                        .on_press(Message::ToggleFile(file_key.clone()))
                );
                
                // Level 3: Hunks in file (if expanded)
                if view.expanded_files.contains(&file_key) {
                    for (hunk_idx, hunk) in file.hunks.iter().enumerate() {
                        let hunk_key = format!("{}:hunk_{}", file_key, hunk_idx);
                        
                        let hunk_row = row![
                            text("        ├─ "),
                            if view.expanded_hunks.contains(&hunk_key) {
                                text("▼")
                            } else {
                                text("▶")
                            },
                            text(&hunk.summary),
                            text(format!("(lines {}-{})", hunk.lines_start, hunk.lines_end))
                                .size(11)
                                .color(Color::GRAY),
                        ]
                        .spacing(5)
                        .padding(6);
                        
                        content = content.push(
                            button(hunk_row)
                                .on_press(Message::ToggleHunk(hunk_key.clone()))
                        );
                        
                        // Level 4: Actual code (if expanded)
                        if view.expanded_hunks.contains(&hunk_key) {
                            // Load diff if not cached
                            let cache_key = format!("{}:{}", commit.commit_id, file.file_path);
                            if !view.loaded_diffs.contains_key(&cache_key) {
                                // Trigger lazy load
                            }
                            
                            if let Some(diff) = view.loaded_diffs.get(&cache_key) {
                                content = content.push(
                                    container(
                                        text_editor(&diff.content)
                                            .font(Font::MONOSPACE)
                                    )
                                    .padding(10)
                                    .style(theme::Container::Box)
                                );
                            }
                        }
                    }
                }
            }
        }
    }
    
    scrollable(content).into()
}

// Action Buttons
pub fn review_actions_view(view: &DiffView) -> Element<Message> {
    row![
        button("✓ Accept All").on_press(Message::AcceptAll),
        button("✗ Reject All").on_press(Message::RejectAll),
        button("📝 Feedback").on_press(Message::ShowFeedbackModal),
    ]
    .spacing(10)
    .into()
}
```

---

### Component 4: Real-Time Streaming

**Responsibility**: WebSocket connection, update handling, error display

**Implementation**:

```rust
// src/services/stream_handler.rs

pub struct StreamHandler {
    websocket: Option<WebSocketStream>,
    connection_state: ConnectionState,
    latest_update: Option<StreamUpdate>,
}

#[derive(Debug, Clone)]
pub enum StreamUpdate {
    StatusUpdate {
        stage_id: String,
        status: String,
        progress_percent: u32,
        metrics: StatusMetrics,
    },
    WorkflowComplete {
        commits: Vec<CommitMetadata>,
        total_changes: TotalChanges,
    },
    Error {
        error_code: String,
        message: String,
    },
}

impl StreamHandler {
    pub fn connect(&mut self, stream_url: &str) -> Command<Message> {
        Command::perform(
            connect_websocket(stream_url.to_string()),
            Message::StreamConnected
        )
    }
    
    pub fn handle_message(&mut self, data: String) -> Command<Message> {
        let update: StreamUpdate = serde_json::from_str(&data)?;
        
        match update {
            StreamUpdate::StatusUpdate { stage_id, status, progress_percent, metrics } => {
                self.latest_update = Some(update);
                Command::perform(
                    async {},
                    |_| Message::UpdateUI
                )
            }
            StreamUpdate::WorkflowComplete { commits, total_changes } => {
                self.latest_update = Some(update);
                Command::perform(
                    async {},
                    |_| Message::WorkflowComplete
                )
            }
            StreamUpdate::Error { error_code, message } => {
                Command::perform(
                    async {},
                    |_| Message::ShowError(message)
                )
            }
        }
    }
}

pub async fn connect_websocket(url: String) -> Result<WebSocketStream, Error> {
    let (ws_stream, _) = tokio_tungstenite::connect_async(&url).await?;
    Ok(ws_stream)
}

// Footer Status Display
pub fn status_footer(stream: &StreamHandler) -> Element<Message> {
    if let Some(StreamUpdate::StatusUpdate { stage_id, status, progress_percent, metrics }) = &stream.latest_update {
        row![
            text(status),
            progress(0.0..=100.0, *progress_percent as f32),
            text(format!("{}%", progress_percent)),
            text(format!("⚡ {:.1} tokens/sec", metrics.inference_speed_tokens_per_sec))
                .size(12)
                .color(Color::GRAY),
        ]
        .spacing(10)
        .padding(10)
        .into()
    } else {
        text("Ready").into()
    }
}
```

---

## STATE MANAGEMENT

### Elm Architecture Pattern

```rust
// src/state.rs

pub struct State {
    // Workspace
    current_workspace: Option<WorkspaceContext>,
    workspace_config: Option<WorkspaceConfig>,
    
    // Configuration
    config_bundle: Option<ConfigBundle>,
    
    // Workflow execution
    selected_workflow: Option<String>,
    user_query: String,
    current_execution_id: Option<String>,
    stream_handler: StreamHandler,
    
    // Diff view
    diff_view: DiffView,
    
    // UI state
    is_loading: bool,
    error_message: Option<String>,
}

// Message enum: All possible user interactions
#[derive(Debug, Clone)]
pub enum Message {
    // Workspace
    OpenWorkspaceDialog,
    WorkspaceSelected(PathBuf),
    ConfigsLoaded(ConfigBundle),
    
    // Workflow
    WorkflowSelected(String),
    QueryInput(String),
    SubmitWorkflow,
    WorkflowSubmitted(Result<WorkflowSubmitResponse>),
    
    // Streaming
    StreamConnected(WebSocketStream),
    StreamMessage(StreamUpdate),
    WorkflowComplete,
    
    // Diff View
    ToggleCommit(String),
    ToggleFile(String),
    ToggleHunk(String),
    LoadDiff(String),  // Lazy load code
    DiffLoaded(DiffContent),
    
    // User Actions
    AcceptAll,
    RejectAll,
    ShowFeedbackModal,
    SubmitFeedback(String),
    
    // Errors
    ShowError(String),
}

// Update function: Pure state transitions
pub fn update(state: &mut State, message: Message) -> Command<Message> {
    match message {
        Message::WorkspaceSelected(path) => {
            state.current_workspace = Some(WorkspaceContext::from_path(&path));
            state.workspace_config = WorkspaceManager::load_config(&path).ok();
            Command::perform(
                load_config_files(&path),
                Message::ConfigsLoaded
            )
        }
        
        Message::SubmitWorkflow => {
            state.is_loading = true;
            // Build request and submit
            Command::perform(
                submit_workflow_request(...),
                Message::WorkflowSubmitted
            )
        }
        
        Message::StreamMessage(update) => {
            match update {
                StreamUpdate::StatusUpdate { .. } => {
                    state.diff_view.latest_update = Some(update);
                    Command::none()
                }
                StreamUpdate::WorkflowComplete { commits, .. } => {
                    state.diff_view.commits = commits;
                    state.is_loading = false;
                    Command::none()
                }
                StreamUpdate::Error { message, .. } => {
                    state.error_message = Some(message);
                    Command::none()
                }
            }
        }
        
        // ... other messages
    }
}
```

---

## USER FLOW & INTERACTIONS

### Happy Path: Feature Implementation

```
1. User launches Agentic IDE
   └─ UI shows: "Select Workspace" prompt

2. User clicks "Browse"
   └─ Native file dialog opens

3. User selects /home/user/my-project
   ├─ UI loads .agentic-ide/config.yaml (or uses defaults)
   ├─ UI loads config/ files (agents.yaml, workflows.yaml, etc)
   └─ UI displays: Workflow selector + query input

4. User selects "feature_implementation" workflow
   └─ UI shows stages: Code Gen, Test Gen, Security

5. User types: "Implement JWT authentication with 1-hour expiration"
   └─ UI enables Submit button

6. User clicks Submit
   ├─ UI sends request to backend with complete config
   ├─ Backend returns execution_id
   ├─ UI opens WebSocket stream
   └─ Footer shows: "Routing workflow..."

7. Real-time updates stream in
   ├─ "Retrieving context..." (2s)
   ├─ "Generating code..." (60s, shows progress)
   ├─ "Generating tests..." (50s)
   └─ "Workflow complete"

8. Footer shows: "✓ 2 commits, 227 additions"

9. UI displays hierarchical diff view
   ├─ Commit 1: "feat: Implement JWT authentication with 1-hour expiration"
   │  ├─ src/auth/jwt_handler.py (+142 lines)
   │  │  └─ [Click to zoom → shows actual code]
   │  └─ [✓ Accept] [✗ Reject] [💬 Annotate]
   │
   ├─ Commit 2: "test: Add JWT authentication tests"
   │  ├─ tests/test_jwt.py (+85 lines)
   │  │  └─ [Click to zoom]
   │  └─ [✓ Accept] [✗ Reject] [💬 Annotate]
   │
   ├─ [✓ Accept All] [✗ Reject All] [📝 Feedback]

10. User clicks "✓ Accept All"
    ├─ UI sends: POST /api/workflow/{execution_id}/apply
    ├─ Commits applied to workspace
    ├─ Git branch merged to main
    └─ UI shows: "✓ Changes applied to workspace"

11. User now sees JWT code in their project
```

### Error Path: Generation Fails

```
1-7. Same as happy path...

8. Backend: Code Gen fails (syntax error)
   ├─ Retrieval Agent invoked with enhanced context
   ├─ Code Gen retries
   └─ Success on second attempt

9. UI shows: "⚠️ Retry (1/3 attempts)"
   └─ Then proceeds to completion

Alternative: Max retries exceeded
├─ UI shows error: "Code generation failed after 3 attempts"
└─ User can: Try again / Provide feedback / Cancel
```

### Modification Path: User Feedback

```
1-10. User sees diff view

11. User clicks "📝 Feedback" on test commit
    ├─ Modal opens: "Add tests for error cases"
    └─ User types feedback

12. User submits feedback
    ├─ Backend restarts workflow
    ├─ Orchestrator receives original query + feedback
    ├─ Retrieval executes with enhanced context
    ├─ Code Gen regenerates with feedback
    ├─ Test Gen regenerates better tests
    └─ UI shows: "✓ Regenerated with your feedback"

13. New diff view shows improved tests
```

---

## DATA MODELS

### Core Models

```rust
// src/models.rs

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceContext {
    pub workspace_id: String,
    pub working_dir: String,
    pub language: String,
    pub framework: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceConfig {
    pub version: String,
    pub workspace: WorkspaceInfo,
    pub retrieval: RetrievalSettings,
    pub agents: HashMap<String, AgentSettings>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommitMetadata {
    pub commit_id: String,
    pub agent: String,
    pub message: String,
    pub files_changed: usize,
    pub additions: usize,
    pub deletions: usize,
    pub files: Vec<FileChange>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileChange {
    pub file_path: String,
    pub change_type: ChangeType,
    pub additions: usize,
    pub deletions: usize,
    pub hunks: Vec<HunkSummary>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ChangeType {
    Created,
    Modified,
    Deleted,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HunkSummary {
    pub hunk_id: String,
    pub lines_start: usize,
    pub lines_end: usize,
    pub summary: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiffContent {
    pub commit_id: String,
    pub file_path: String,
    pub diff: String,  // Unified diff
    pub hunks: Vec<DiffHunk>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiffHunk {
    pub hunk_id: String,
    pub old_start: usize,
    pub old_count: usize,
    pub new_start: usize,
    pub new_count: usize,
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkflowSubmitRequest {
    pub workflow_id: String,
    pub workflow_type: String,
    pub user_query: String,
    pub workflow_config: serde_json::Value,
    pub agents_config: serde_json::Value,
    pub retrieval_config: serde_json::Value,
    pub mcp_config: serde_json::Value,
    pub workspace_context: WorkspaceContext,
    pub correlation_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkflowSubmitResponse {
    pub execution_id: String,
    pub workflow_id: String,
    pub status: String,
    pub streaming_url: String,
}
```

---

## CONFIGURATION MANAGEMENT

### Config File Loading

```rust
// src/services/config_loader.rs

pub struct ConfigLoader;

impl ConfigLoader {
    pub async fn load_all_configs(workspace_path: &Path) -> Result<ConfigBundle> {
        let config_dir = workspace_path.parent()
            .ok_or("Invalid workspace path")?
            .join("config");
        
        let agents = Self::load_yaml::<HashMap<String, AgentConfig>>(
            &config_dir.join("agents.yaml")
        )?;
        
        let workflows = Self::load_yaml::<HashMap<String, WorkflowConfig>>(
            &config_dir.join("workflows.yaml")
        )?;
        
        let retrieval = Self::load_yaml::<RetrievalConfig>(
            &config_dir.join("retrieval.yaml")
        )?;
        
        let mcp_integration = Self::load_yaml::<McpConfig>(
            &config_dir.join("mcp_integration.yaml")
        )?;
        
        Ok(ConfigBundle {
            agents,
            workflows,
            retrieval,
            mcp_integration,
        })
    }
    
    fn load_yaml<T: for<'de> Deserialize<'de>>(path: &Path) -> Result<T> {
        let content = std::fs::read_to_string(path)?;
        serde_yaml::from_str(&content)
            .map_err(|e| format!("YAML parse error in {}: {}", path.display(), e).into())
    }
}
```

---

## API COMMUNICATION

### HTTP Client Setup

```rust
// src/services/api_client.rs

pub struct ApiClient {
    client: reqwest::Client,
    base_url: String,
}

impl ApiClient {
    pub fn new(backend_url: &str) -> Self {
        Self {
            client: reqwest::Client::new(),
            base_url: backend_url.to_string(),
        }
    }
    
    pub async fn submit_workflow(
        &self,
        request: WorkflowSubmitRequest,
    ) -> Result<WorkflowSubmitResponse> {
        let response = self.client
            .post(format!("{}/api/workflow/submit", self.base_url))
            .json(&request)
            .send()
            .await?;
        
        if response.status().is_success() {
            response.json().await
        } else {
            Err(format!("Backend error: {}", response.status()).into())
        }
    }
    
    pub async fn get_workflow_diff(
        &self,
        execution_id: &str,
        commit_id: &str,
    ) -> Result<DiffContent> {
        let response = self.client
            .get(format!(
                "{}/api/workflow/{}/commit/{}/diff",
                self.base_url, execution_id, commit_id
            ))
            .send()
            .await?;
        
        response.json().await
    }
    
    pub fn stream_workflow_updates(
        &self,
        stream_url: &str,
    ) -> impl futures::Stream<Item = Result<StreamUpdate>> {
        // WebSocket streaming
        futures::stream::unfold(
            None,
            move |_| {
                let url = stream_url.to_string();
                async move {
                    // Connect to WebSocket and yield updates
                }
            }
        )
    }
}
```

---

## DEPLOYMENT & BUILD

### Build Configuration

```toml
# Cargo.toml

[package]
name = "agentic-ide-gui"
version = "1.0.0"
edition = "2021"

[dependencies]
iced = { version = "0.10", features = ["debug", "wgpu"] }
iced_wgpu = "0.10"
tokio = { version = "1", features = ["full"] }
reqwest = { version = "0.11", features = ["json"] }
tokio-tungstenite = "0.20"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
serde_yaml = "0.9"
tracing = "0.1"
tracing-subscriber = "0.3"

[[bin]]
name = "agentic-ide"
path = "src/main.rs"
```

### Build & Run

```bash
# Development
cargo build
cargo run

# Release (optimized)
cargo build --release
./target/release/agentic-ide

# Nix flake (for NixOS deployment)
nix run .#agentic-ide-gui

# Package as executable
cargo install --path .
agentic-ide
```

---

## IMPLEMENTATION ROADMAP

### Phase 1: UI Shell & Configuration (Weeks 1-2, 60 hours)

**Week 1**:
- [ ] Iced app skeleton (main window, layout)
- [ ] Workspace selector (file browser)
- [ ] YAML config parsing (serde_yaml)

**Week 2**:
- [ ] Workflow selector dropdown
- [ ] User query input field
- [ ] Config display (agents, workflows)
- [ ] Basic error handling

**Deliverable**: GUI loads workspace and configs, displays workflow options

---

### Phase 2: API Communication & Streaming (Weeks 2-3, 70 hours)

- [ ] Request builder (WorkflowSubmitRequest)
- [ ] HTTP client (reqwest)
- [ ] WebSocket setup (tokio-tungstenite)
- [ ] Message parsing (serde_json)
- [ ] Error handling & retry

**Deliverable**: GUI can submit requests and receive streaming updates

---

### Phase 3: Hierarchical Diff View (Weeks 3-5, 120 hours)

- [ ] Diff view component
- [ ] Commit summary level
- [ ] File listing level
- [ ] Hunk summary level
- [ ] Code lazy-loading (on-demand)
- [ ] Syntax highlighting

**Deliverable**: User can navigate diff hierarchy, load code on demand

---

### Phase 4: User Interactions & State Management (Weeks 5-6, 80 hours)

- [ ] Accept/reject/feedback actions
- [ ] State management (Elm architecture)
- [ ] Modal dialogs
- [ ] Feedback submission
- [ ] Change application

**Deliverable**: User can provide feedback, changes apply to workspace

---

### Phase 5: Real-Time Updates & Status (Weeks 6-7, 70 hours)

- [ ] Footer status bar
- [ ] Progress indicator
- [ ] Streaming update handling
- [ ] Error display
- [ ] Workflow completion animation

**Deliverable**: Real-time updates display smoothly, user sees progress

---

### Phase 6: UI Polish & Responsive Design (Weeks 7-8, 60 hours)

- [ ] Responsive layout (resizable panels)
- [ ] Theme support (light/dark)
- [ ] Keyboard shortcuts
- [ ] Search/filter in diff view
- [ ] Workspace history

**Deliverable**: Professional, polished UI experience

---

### Phase 7: Testing & Optimization (Weeks 8-9, 100 hours)

- [ ] Unit tests (component logic)
- [ ] Integration tests (API calls)
- [ ] Performance optimization (rendering)
- [ ] GPU utilization (Wgpu)
- [ ] Documentation

**Deliverable**: Test suite passing, performance optimized, documented

---

## DEVELOPMENT GUIDELINES

### Code Organization

```
src/
├── main.rs                    # App entry point
├── app.rs                     # Main Elm-style component
├── message.rs                 # Message enum
├── state.rs                   # Application state
│
├── components/
│   ├── workspace_manager.rs   # Workspace selection
│   ├── workflow_interface.rs  # Config & submission
│   ├── diff_view.rs           # Hierarchical diff
│   └── stream_handler.rs      # Real-time updates
│
├── services/
│   ├── api_client.rs          # HTTP/WebSocket
│   ├── config_loader.rs       # YAML loading
│   └── git_ops.rs             # Git operations (future)
│
├── models.rs                  # Data models
├── themes.rs                  # UI themes
└── utils.rs                   # Helpers
```

### Elm Architecture Pattern

```rust
// Three pillars: State → Update → View

// 1. STATE: Data model
pub struct State {
    workspace: Option<WorkspaceContext>,
    config: Option<ConfigBundle>,
    // ...
}

// 2. UPDATE: Pure functions handling messages
pub fn update(state: &mut State, message: Message) -> Command<Message> {
    // State transitions (no side effects)
    // Return commands for async operations
}

// 3. VIEW: Pure rendering
pub fn view(state: &State) -> Element<Message> {
    // Render UI (no state mutations)
}

// Benefits:
// - Predictable state changes
// - Easy debugging (message history)
// - Testable (pure functions)
// - Supports time-travel debugging
```

### Async Pattern with Tokio

```rust
pub async fn submit_workflow_request(
    request: WorkflowSubmitRequest,
    client: ApiClient,
) -> Result<WorkflowSubmitResponse> {
    // Non-blocking network call
    client.submit_workflow(request).await
}

// In update():
Command::perform(
    submit_workflow_request(request, api_client),
    Message::WorkflowSubmitted  // Callback message
)
```

### Error Handling

```rust
// Use Result types consistently
pub fn load_config(path: &Path) -> Result<ConfigBundle> {
    // ...
}

// Display errors to user
Message::ShowError(err.to_string())

// Logging with tracing
tracing::info!("Workflow submitted: {}", execution_id);
tracing::error!("API error: {}", err);
```

---

**END OF UI SPECIFICATION**

This document is your complete guide to implementing the frontend GUI. Every component is detailed, every data flow is specified, and every interaction is documented.

**Questions?** Refer back to:
- Section 3 (Components) for implementation details
- Section 5 (User Flow) for interaction patterns
- Section 7 (Data Models) for data structures
- Section 10 (Roadmap) for phase breakdown

