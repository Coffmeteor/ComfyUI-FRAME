# Version 0.1.0 validation scope

The package has 27 unit tests covering configuration validation, immutable
snapshots, user-defined Boolean schemas, named groups and exclusivity, native
LoRA graph loading, model-only versus model+CLIP application, trigger precedence
and removal, paths, changed/missing files, source selection, website publication
updates, midnight behavior, request bounds and preservation of complete text.

A real ComfyUI 0.43.0 frontend constructed and serialized the phone workflow,
reloaded it, and produced an identical API graph. It contained five cards for
the tested configuration: source, prompt/quality and three local LoRA groups.
Every editable API value was a prompt string or Boolean; configuration fields
were absent. The desktop editor was also opened in the test browser.

Linux GPU acceptance used newly generated ceramic-teapot still lifes, with no
historical people or reference images. Native execution covered:

| Case | Observed result |
|---|---|
| Base, 1 MP, fixed seed | Successful 832×1248 output, no active LoRA |
| One configured style LoRA | Successful 832×1248 output, active LoRA/trigger receipt |
| SD redraw + face-detail option + SeedVR2 | Successful 2048×3072 output |

All eight quality combinations were prepared as native graphs. The combined
test proves their execution chain; its still life had no face, so it does not
establish face-identity fidelity or the quality of a detected-face refinement.
The tested optional dependencies were already installed; no package or weight
upgrade was performed.

The optional ComfyLink patch passed all 589 plugin tests. This includes limited
shared-prompt mutation checks and WebP metadata preservation. Shared-account
execution on a physical phone is not represented as an automated pass.

Windows and Linux unit jobs are configured in CI. Linux GPU execution was
tested; Windows GPU execution and physical phone rendering remain user-side
acceptance. Registry upload success must be distinguished from Registry review
and Manager indexing.
