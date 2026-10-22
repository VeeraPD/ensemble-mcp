# Example: Swift package + iPadOS app

Layout this config assumes (`Core/` is the lead's, no role owns it):

```
MyKit/Sources/MyKit/{Core,UI,Intelligence,Storage}/
MyKit/Tests/
App/
```

This is the shape the original project used: the lead writes protocols and value types in `Core/`, four roles implement against them in parallel, then the lead runs `cd MyKit && swift build && swift test`.

Copy `ensemble.json` and `docs/` to your project root and adjust the paths.
