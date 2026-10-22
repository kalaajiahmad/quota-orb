# Security

Do not post credentials or private diagnostics in public issues. For an implementation vulnerability, use the repository's private vulnerability-reporting feature if available. If private reporting is unavailable, open a minimal issue requesting a private reporting channel without exploit details or private data.

Revoke exposed credentials through their issuing service. Deleting a public commit does not revoke a credential or guarantee removal from clones and caches.

The device is a USB peripheral. Use trusted hosts, validate the board target before flashing, and preserve firmware backups privately. No remote update service is implemented.

Layout imports accept bounded, validated JSON and select only widget IDs in the reviewed registry. They do not load modules, fetch plugins, or execute scripts. Source widgets are ordinary application code with process privileges, not sandboxed extensions; review them as code. Report any import path that crosses this data/code boundary privately.
