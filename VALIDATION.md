# Version 0.2.4 validation scope

Version 0.2.4 gives newly saved recipes an explicit **Append manual text** switch, off by default. Online and local libraries use only the selected entry unless this switch is enabled; manual-only mode still uses the text field. Six additional Python tests cover all export languages, non-Boolean rejection, manual-only mode, cached online/local selection without redrawing, immutable policy bindings and unchanged legacy snapshots.

Native frontend construction and server previews confirmed off/on/off prompt composition while retaining the manual field and the selected local entry. A real 1184×1760 GPU output retained the nonempty manual field in its workflow, while its executed prompt and source receipt excluded that text and recorded `manual_text_ignored: true`. The owner workflow was migrated with its latest submitted controls and cached selections preserved.

The desktop editor supports Auto (ComfyUI locale), English and Chinese, with a separate English/Chinese/bilingual export setting. Existing language-less snapshots retain their exact Chinese schema. Four language tests cover English defaults, immutable language bindings, legacy restoration, normalized controls and preservation of custom names. Two JavaScript tests cover locale resolution and label translation.

Native desktop acceptance confirmed Auto on an English ComfyUI locale, switching to Chinese and back without losing a draft, saving/reopening an English workflow, and native construction of bilingual menus. English and bilingual previews normalize to identical sampler/canvas/prompt settings. One English-control GPU job completed at 832×1248 with seed 0; prior Chinese snapshots remain unchanged. Public desktop screenshots and the downloadable guide use English only.

The portable starter uses only the static `FrameSetup` node and native Markdown
notes, with Manager/Registry dependency metadata. It contains no machine-local
snapshot IDs or model/LoRA bindings. Its desktop button opens the recipe editor;
the generated-workflow button opens the saved local graph. No installer script
is included.

A physical phone report for 0.2.0 showed both source menus as editable text
fields. Desktop combo rendering did not prove mobile rendering. Version 0.2.1
emits complete two-part enum specs with explicit defaults and option lists;
the same snapshot IDs and selection semantics are preserved. The schema contract
is checked in the unit suite. Physical phone dropdown rendering requires a
fresh node-definition download. The owner subsequently confirmed that both
dropdowns work on the physical phone.

The package has 49 Python unit tests covering the portable starter, configuration validation, immutable
snapshots, user-defined Boolean schemas, named groups and exclusivity, native
LoRA graph loading, model-only versus model+CLIP application, trigger precedence
and removal, paths, changed/missing files, source selection, website publication
updates, midnight behavior, request bounds and preservation of complete text.

A real ComfyUI 0.43.0 frontend constructed and serialized the phone workflow,
reloaded it, and produced an identical API graph. It contained five cards for
the tested configuration: source, prompt/quality and three local LoRA groups.
Version 0.2.0 exposes two source/mode menus, one prompt and Boolean switches;
configuration fields are absent. The real desktop editor's file picker imported
a two-entry UTF-8 .txt, saved it into the phone source menu, and read the saved
workflow back. Test fixtures were removed from the owner's final recipe.

New tests cover line/block formats, UTF-8 BOM, CRLF, comments, bounds, immutable
library versions, selected-library isolation, two-menu schemas, persistent reuse,
random-to-reuse transitions, separate source/recipe state, network failure
preserving the current prompt and image seeds independent of selected text.
The actual public website's four pools each passed reuse/random/reuse checks.
An actual 1,656,078-byte import request also succeeded; cross-origin writes and
invalid text were rejected.

Two real queued Linux GPU jobs used the same local selected prompt in reuse
mode. Both completed at 832×1248 with different image seeds and different output
hashes. Native preview also proved random mode changes the selected local entry
and switching back to reuse keeps that newest entry. Online acceptance reads
prompt data without generating images from unreviewed random website entries.

Generation-chain acceptance from 0.1.0 used newly generated ceramic-teapot still lifes, with no
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
tested; Windows GPU execution remains user-side acceptance. Phone dropdown
rendering has owner confirmation; that does not claim full shared-account phone
execution coverage. Registry upload success must be distinguished from Registry review
and Manager indexing.
