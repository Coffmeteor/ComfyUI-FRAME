# Optional ComfyLink 0.2.7 compatibility

The node package runs on ComfyUI without this patch. For ComfyLink 0.2.7, this
small optional patch adds two integrations:

- Shared jobs may change only `FramePrompt.text` or the `text` field of a
  snapshot-bound `FrameKrea2_<20 hex digits>` class, up to 16,000 characters.
  Published node types, connections, recipe versions and other string fields
  stay immutable under the existing template validation.
- WebP encoding reads the saved FRAME receipt's resolved base prompt only when
  its recipe ID matches the job's exact snapshot class. This preserves automatic
  triggers and online prompt text in the phone's prompt metadata. Other jobs
  retain their existing metadata handling.

This patch does not enable sharing, change pairing or alter transport. It is not
applied automatically. For the supported plugin checkout, audit existing local
changes, then use Git from the **ComfyUI-ComfyLink** directory:

```bash
git apply --check /path/to/ComfyUI-FRAME/compat/comfylink-0.2.7.patch
git apply /path/to/ComfyUI-FRAME/compat/comfylink-0.2.7.patch
```

Restart ComfyUI while idle. A patch already integrated upstream may fail the
check; inspect the installed source rather than forcing it. Version 0.2.7 plus
this patch passed the 589-test plugin suite, including focused FRAME text and
WebP tests. Physical shared-account execution is a separate acceptance step.

The upstream ComfyLink code is MIT licensed; see `LICENSE-ComfyLink.txt`.
