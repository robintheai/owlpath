Owlpath 1.0.1 — fewer disconnects, same exit IP.

- When the connection stalls, Owlpath now checks why before reconnecting. If your location still works, it restarts the connection on the same location, so the exit IP does not change. Before, a short stall switched to another location and back three minutes later.
- When the network itself is down (for example right after waking the Mac), Owlpath waits for it instead of switching locations. Traffic stays blocked until it returns.
- A subscription refresh that only renames your location no longer reconnects.
