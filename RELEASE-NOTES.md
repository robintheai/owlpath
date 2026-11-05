Owlpath 1.0.0 — a minimal proxy client for researchers.

- Paste a subscription link and press Connect. The whole computer uses the proxy (TUN on Mac and Windows).
- While connected or reconnecting, traffic never falls back to your own network. If no location works, websites wait instead of loading without the proxy. Disconnect to use your network directly.
- When a location stops working, Owlpath tests the others through their own connections and switches to one that works.
- Subscriptions saved by an earlier client of this kind on the same computer are imported on first launch.

Mac: the first Connect asks for macOS permission once to install the network service. The packages are not notarized; see INSTALL.md if macOS blocks the first launch.
