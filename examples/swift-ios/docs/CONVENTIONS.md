Shared rules for every sub-agent.

- Swift 6 language mode, strict concurrency. Prefer async/await and actors; no Combine unless required.
- Minimum deployment target iPadOS 18. Newer-OS-only APIs go behind `#available` with a working fallback. Public Apple APIs only. If you are not certain an API exists with the exact signature you use, do not invent it: write a protocol seam and a TODO under NOTES.
- Pure logic must not import UIKit, so it compiles and tests on macOS. Put platform code behind protocols defined in Core/.
- Do NOT edit files in Core/. If a contract is wrong or missing something, say so under NOTES; do not work around it.
- Implement exactly the task. No extra features, no refactors outside your owned paths, no new dependencies.
- No comments unless the reason is non-obvious. No placeholder or stub bodies unless the task says so.
- Wrap files importing UIKit or other iOS-only APIs in `#if canImport(UIKit)` so `swift build` still works on macOS.
