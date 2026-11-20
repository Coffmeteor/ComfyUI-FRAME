# FRAME Nodes — Workflow Generator for ComfyUI and ComfyLink

Choose **Krea2** or **MOSS**, configure your models and LoRAs on the computer, and generate a workflow for ComfyUI and ComfyLink. Both families support FRAME prompt libraries, imported text libraries and batch prompt selection.

## Install, then open the generator

1. In **ComfyUI Manager**, search **frame-nodes** and install version **0.3.7** or newer. Restart ComfyUI and refresh the browser. If the version is still being indexed, use the release ZIP.
2. Open the **ComfyUI menu at the top left → FRAME → Recipe Setup**. That opens the generator; you do not need to load a workflow first.
3. Alternatively, open the included **workflows/FRAME Krea2 - Start Here.json** and click **Configure models & LoRAs**. This starter is a shortcut to the same generator.

For manual installation, download **FRAME-Nodes-0.3.7.zip** from the GitHub release, extract its **ComfyUI-FRAME** folder into **ComfyUI/custom_nodes/**, and restart. Keep one installed copy. Manager handles declared dependencies during installation; a manually installed Windows environment may need the declared timezone-data dependency.

Registry: https://registry.comfy.org/nodes/frame-nodes
Source: https://github.com/Coffmeteor/ComfyUI-FRAME

## Configure Krea2 on the computer

1. Choose **Krea2** as the model family. In **Models (first-time setup)**, choose your Krea2 diffusion model, text encoder and VAE. The menus list files already installed in ComfyUI.
2. In **Krea2 sampling**, set steps, sampler and scheduler. Defaults are 8 steps, CFG 1 and Euler ancestral / beta; adjust them for your model.
3. In **My LoRAs**, add a group, choose each LoRA file and give it a readable switch name. Set model strength, CLIP strength and application stages. Use CLIP strength 0 for model-only LoRAs.
4. Choose **auto**, **manual** or **none** for triggers. Auto reads explicit trigger metadata; enter the author's trigger words manually if no metadata is available. Mark a group **Allow only one active LoRA** when its choices should be exclusive.
5. Optionally import local text libraries. Choose the interface language and the exported **Workflow labels** language separately.
6. Give the workflow a name and choose its save path. Click **Save recipe & generate workflow**, then **Open generated workflow**.
7. In the generated workflow, choose your prompt source, enable the LoRAs you want, adjust their strengths and quality options, and click **Run**.

Requires ComfyUI 0.43.0 or newer and your own compatible models. The generated workflow refers to a recipe saved on this computer. Other users should install the generator and configure their own files; do not send them your machine-specific recipe as a universal workflow.

Newly saved recipes have one batch-selection card. Its field names and menu choices follow the exported workflow language. The main card contains prompt, quality and replay controls; legacy batch and internal prepared-JSON fields are not exposed. Older recipe snapshots retain their original interface.

## Configure MOSS on the computer

1. Choose **MOSS** under **Model family**. Select your installed MOSS-Image diffusion model, compatible Qwen 3.5 text encoder, and FLUX.2 VAE. Use a ComfyUI build with native `moss_image` support. [ComfyUI MOSS-Image setup](https://docs.comfy.org/tutorials/image/moss-image/moss-image)
2. In **MOSS sampling**, set the sampler for your checkpoint. The starting settings are 25 steps, CFG 2.5, ER-SDE, simple, and flow shift 5. You can also set a negative prompt.
3. In **MOSS LoRA Stack**, add your compatible model-only LoRA files and choose their trigger behavior. The phone workflow shows one card with four slots. Each slot lets you choose a configured LoRA and set its strength. **None** or zero strength skips the slot. Active LoRAs apply in slot order.
4. Optionally select local prompt libraries, then save and open the workflow. In **MOSS · Prompt & Resolution**, choose from seven presets, including portrait, square, landscape and lower-resolution previews.

MOSS and Krea2 each keep their own last saved recipe and default workflow path. Share the installer and setup guide with other ComfyUI users so they can generate a workflow against their own models and libraries.

## Language options

The desktop editor supports **Auto**, **English** and **Chinese**. Auto follows the ComfyUI interface locale, with English as the fallback. You can change this preference without losing unsaved form values.

**Workflow labels** is a separate setting: choose **English**, **Chinese** or **Bilingual**. New installations default to English. Save the recipe and sync its generated workflow to apply these labels in ComfyLink. This export setting does not rely on the phone app translating custom nodes. Your own group names, LoRA switch names, library names and prompts stay as entered.

Existing Chinese workflows retain their original field names and recipe bindings. Updating the extension does not rewrite existing workflows. To change their labels, save a new recipe with the desired export language and use its newly generated workflow.

All instructions and desktop screenshots on this resource use the English interface.

## ComfyLink phone setup

1. Save and generate the workflow on desktop.
2. FRAME refreshes the paired ComfyLink backend node definitions when saving a recipe. Check the save result. If it reports a refresh failure, restart ComfyUI while idle or refresh backend node definitions before uploading.
3. Upload or update the generated workflow in the desktop ComfyLink panel.
4. Sync the workflow on your phone.
5. Use **Prompt source** and **Selection mode** on either workflow. On MOSS, set **Resolution** and choose up to four entries in **MOSS LoRA Stack**. On Krea2, use the quality and named LoRA switches.

If a source or mode field appears as an editable text box, refresh the phone's backend node/model definitions, then sync the workflow again. Workflow upload and node-definition refresh are separate operations; FRAME now performs the latter automatically on recipe save when the installed ComfyLink plugin supports it. This fixes new snapshot nodes appearing as text fields after a hot save. Offline, unpaired or unsupported plugins leave the desktop recipe usable and show a refresh warning instead of reporting success. No pairing permissions are changed. After changing model bindings, LoRA groups, selected libraries or workflow language, generate and sync the new workflow again.

Krea2 file selection, CLIP strength, trigger editing and application stages are configured on the computer. Krea2 enable switches and model strengths are available on the phone. Shared-backend execution may require a compatible ComfyLink version; see the source repository's compatibility notes.

## Online and local prompt sources

Choose exactly one source:

- **Manual prompt**: use your text only.
- **FRAME Original · Full library** or **FRAME Original · Latest update**.
- **FRAME Rewrite · Full library** or **FRAME Rewrite · Latest update**.
- **Local · your library name**: use an imported text library.

Original and Rewrite remain separate catalogs. Latest update follows the website's most recently published update batch, including daily additions. It does not become empty simply because your phone passes midnight. Website: https://frame.coffmetoer.tech/

You can keep manual prompt text while using a library. It is ignored by default; enable **Append manual text** in the source card to include it as a supplement. Manual-only mode always uses your text. The final prompt order is enabled LoRA triggers, the complete selected library entry, then your supplement. Turning a LoRA off removes its automatic trigger injection while preserving your own text. The append switch does not erase the manual field or change the current library selection. Existing pre-0.2.4 recipes retain their original automatic-append behavior until resaved and synced.

Online selection reads the public FRAME catalog API. It does not upload your prompt, images, model inventory or account credentials to FRAME. Manual and imported local-library modes work without that website.

## Reuse a prompt or draw another

- **Reuse current**: the first generation selects an entry; subsequent generations keep it while image seeds can vary. The selection survives restarts.
- **Random each generation**: every generation draws another entry and saves it as the current selection. Switch back to Reuse current to keep one you like.

**Fixed image seed** controls image sampling independently. Each source has its own current prompt within a recipe. Callers using the same backend and recipe share that selection state. A reused online prompt is kept across website updates until you request another draw. Network errors do not silently switch catalogs or replace the current entry.

## Import wildcard text files

Open **Local wildcard libraries**, choose a UTF-8 `.txt`, select **One entry per line** or **Blank-line blocks (multiline)**, and click **Import library**. Tick the imported library, save the recipe and sync the generated workflow.

Limits: 4 MiB per file, 50,000 entries, 32 KiB per entry, and 32 selected libraries per recipe. Whole-line `#` comments are ignored. These are literal text libraries: nested `__references__`, `{A|B}` expressions and scripts are not executed.

## Quality switches and optional dependencies

The default portrait canvas is approximately 2 MP. Choose at most one of **Landscape**, **Square** and **Phone wallpaper**. **1 MP** reduces base resolution.

- **SD redraw** requires Ultimate SD Upscale and a configured upscaler model.
- **Face detail** requires Impact Pack/Subpack and a configured Ultralytics detector.
- **SeedVR2 restoration** requires the corresponding native ComfyUI SeedVR2 nodes, model, VAE and an upscaler model.
- **Alternate model** selects the alternate Krea2 model configured on desktop.

These dependencies are only needed when their switches are enabled. The extension reports missing enabled dependencies explicitly and does not install them silently or change ComfyUI's device/memory policy.

## Gallery and reproducibility

The four sample images were generated from complete entries in FRAME's live Original catalog using FRAME Nodes 0.2.2. The language update does not change that generation chain. The two elevator images reuse one prompt with different image seeds; the jacket collage and cafe outfit use different entries.

Actual settings: Moody Krea Mix Premium, no active LoRAs, 8 steps, CFG 1, Euler a / beta, 1184 x 1760, without redraw, face detail or SeedVR2. Your results depend on your selected model and settings. The style adapters shown in desktop screenshots are configurable examples and their weights are not included.

Actual prompts and settings remain embedded in the public example PNGs. Use the **Seed (exact)** text field or PNG parameters for the full 63-bit image seed, because website numeric fields can round large integers. Machine-local workflow/configuration data has been removed without changing the image pixels. Phone screenshots will be added separately.

Package code is MIT licensed. Model weights, adapters and online content retain their respective terms. Public downloads contain no personal recipe, account pairing information, credentials or model weights. Ordinary local FRAME outputs include prompt/workflow metadata; inspect it before sharing.

Chinese documentation: [README.zh-CN.md](README.zh-CN.md)

## Development

Run `python -m unittest discover -s tests -v` and `node --test tests/test_i18n.mjs`. Registry publication uses `pyproject.toml`; runtime state, model weights, caches, tests and CI are excluded from the Registry archive. See [VALIDATION.md](VALIDATION.md) for acceptance boundaries.

### Phone LoRA strengths

Newly exported mobile recipes keep each LoRA's enable switch and add an adjacent
model-strength number (step 0.05, range -10 to 10). The initial value comes from
the desktop recipe; CLIP strength remains the recipe value. Switching a LoRA off
ignores its number. Exclusive groups retain their single-selection rule. ComfyLink exposes these ordinary FLOAT controls without a phone app update. Old recipe snapshots keep their original Boolean-only contract.
Save/export and sync a new recipe after replacing a LoRA file. The PNG receipt
records the actual model and CLIP strengths used for enabled LoRAs.

## Frozen batches and replay

`batch_count` prepares 1–10 images in a single workflow execution. All source
prompts, seeds, expanded graphs and LoRA settings are resolved and saved under
`ComfyUI/user/frame-nodes/plans` before any image nodes execute. Preparation
failure submits no partial image batch. Each image filename and PNG receipt
contains its `F…-01` item code; the parent `F…` code identifies the whole batch.
Enter either in `replay_code` to reproduce it. Replay ignores current controls
and does not request new library prompts. Restore changed model files before
replay; model signatures are checked, and a changed inference environment may
still affect exact pixels. Keep the plans directory with your private backups.

Desktop ComfyUI and ComfyLink use these controls. Use this workflow's batch count for
a frozen group; ComfyLink's independent app-level repetition submits separate
plans. Advanced callers may supply a `prompt_batch` JSON list with source IDs and revisions. Plan files retain full prompts, so future catalog updates do not
change old tasks. Standard ComfyUI attempt IDs distinguish reruns of one plan.

### Select by permanent FRAME numbers

`catalog_selection` is separate from replay and image seeds:
- **Random IDs each run** draws `batch_count` distinct numbers from the public API
  at the start of every run.
- **Fixed prompt IDs** resolves the comma/newline-separated numbers in `prompt_ids` in order
  on every run. Its count must match `batch_count`. Missing IDs stop the batch;
  they are never silently substituted.
- **Workflow source** retains the existing source/manual controls.

Choose `catalog` and `prompt_format` explicitly. Library and Rewrite each number entries from 1. These FRAME-owned numbers are
allocated once on admission and never reused or renumbered. The chosen catalog
distinguishes Library #1 from Rewrite #1. Fixed selection follows
current content revisions for those IDs. Use `replay_code` only when you also
want the exact saved text, seeds and graph from an earlier image.

ComfyLink displays selection in the dedicated **Batch prompts · Count & Numbers**
node (`批量抽词 · 数量与编号`). Its five scalar controls are required widgets,
so they appear as a normal workflow section instead of optional advanced inputs.
The connected section owns selection values; legacy inline inputs remain supported
for older workflows. Refresh the saved workflow list after upgrading the node pack.

## Version 0.3.7

Adds MOSS as a model family in the generator, with the FRAME prompt library, one four-slot model-only LoRA card, and a seven-preset resolution menu. Existing Krea2 recipes remain available.

## Version 0.3.6

Includes the dedicated batch-selection card, 1–10 prompts per run, random selection or a fixed list of permanent FRAME prompt numbers, frozen generation plans and replay codes. Preserves LoRA strength controls, automatic triggers, manual-prompt supplement behavior and automatic ComfyLink node-definition refresh. Existing private recipes and saved workflows are not rewritten by installation. Regenerate and sync a workflow to expose the new controls.
