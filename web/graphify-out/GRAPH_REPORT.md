# Graph Report - web  (2026-05-17)

## Corpus Check
- 5 files · ~270,132 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 91 nodes · 115 edges · 9 communities (6 shown, 3 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]

## God Nodes (most connected - your core abstractions)
1. `TrafficLawDB` - 8 edges
2. `create_response()` - 6 edges
3. `createNewChat()` - 5 edges
4. `renderSidebar()` - 5 edges
5. `handleSend()` - 5 edges
6. `scrollToBottom()` - 4 edges
7. `processNewFiles()` - 3 edges
8. `get_system_stats()` - 3 edges
9. `processSelectedFile()` - 3 edges
10. `removeImage()` - 3 edges

## Surprising Connections (you probably didn't know these)
- `handleSend()` --calls--> `removeImage()`  [EXTRACTED]
  script.js → script.js  _Bridges community 4 → community 5_

## Communities (9 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (16): adminLink, avatarBtn, currentUserStr, displayRole, displayUsername, dragOverlay, dropdown, imagePreview (+8 more)

### Community 1 - "Community 1"
Cohesion: 0.1
Nodes (16): currentUserStr, dropzone, fileInput, fileList, fileListContainer, files, formData, importBtn (+8 more)

### Community 2 - "Community 2"
Cohesion: 0.17
Nodes (11): answer_with_image_input(), base64ToBGR(), build_graph(), check_progress(), create_response(), get_system_stats(), init_user_db(), process_document() (+3 more)

### Community 4 - "Community 4"
Cohesion: 0.33
Nodes (7): backToHome(), clearAllHistory(), createNewChat(), deleteChat(), loadChat(), removeImage(), renderSidebar()

### Community 5 - "Community 5"
Cohesion: 0.4
Nodes (6): appendMessageUI(), handleDrop(), handleSend(), processSelectedFile(), scrollToBottom(), updateMessage()

### Community 7 - "Community 7"
Cohesion: 0.67
Nodes (3): processNewFiles(), renderFileList(), showStatus()

## Knowledge Gaps
- **33 isolated node(s):** `currentUserStr`, `user`, `menu`, `dropzone`, `fileInput` (+28 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `currentUserStr`, `user`, `menu` to the rest of the system?**
  _35 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._