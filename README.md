# FRAME Krea2 for ComfyLink

Online prompts, automatic LoRA triggers and named phone switches for ComfyUI. Configure your own models and LoRAs on desktop, then generate a compact workflow for ComfyLink. Desktop generation is supported too.

## Install the required custom node

Install **FRAME Nodes** (`frame-nodes`) through **ComfyUI Manager**. It is listed in the official ComfyUI Registry. The portable starter contains the Registry dependency metadata, so Manager's **Install Missing Custom Nodes** can identify it. Restart ComfyUI after installation.

- Registry: https://registry.comfy.org/nodes/frame-nodes
- Source and updates: https://github.com/Coffmeteor/ComfyUI-FRAME

A source ZIP is attached as a fallback: extract its `ComfyUI-FRAME` directory into `ComfyUI/custom_nodes/`, satisfy the declared requirements in your existing ComfyUI environment if needed, and restart. Keep only one installed copy. No installer script or model weights are included. Registry publication and platform review are separate; use the attached source if Manager has not yet received the current release.

Requires ComfyUI 0.43.0 or newer, a compatible Krea2 diffusion model, text encoder and VAE. The complete recipe targets Krea2; generic LoRA and prompt nodes can also be composed with standard ComfyUI workflows.

## Language options

The desktop editor supports **Auto**, **English** and **Chinese**. Auto follows the ComfyUI interface locale, with English as the fallback. You can change this preference without losing unsaved form values.

**Workflow labels** is a separate setting: choose **English**, **Chinese** or **Bilingual**. New installations default to English. Save the recipe and sync its generated workflow to apply these labels in ComfyLink. This export setting does not rely on the phone app translating custom nodes. Your own group names, LoRA switch names, library names and prompts stay as entered.

Existing Chinese workflows retain their original field names and recipe bindings. Updating the extension does not rewrite existing workflows. To change their labels, save a new recipe with the desired export language and use its newly generated workflow.

All instructions and desktop screenshots on this resource use the English interface.

## Configure once on desktop

1. Load **FRAME Krea2 - Start Here.json**.
2. Click **Configure models & LoRAs**, or open **FRAME > Recipe Setup** from the ComfyUI menu.
3. Select your diffusion model, text encoder and VAE. Default sampling is 8 steps, CFG 1, Euler ancestral / beta. Adjust it for your selected model.
4. Add LoRA groups, choose your local files and set readable phone switch names, model/CLIP strengths and application stages. Set CLIP strength to 0 for model-only LoRAs. Enable **Allow only one active LoRA** for mutually exclusive identities.
5. Choose trigger mode: **auto**, **manual** or **none**. Auto reads explicit local sidecar metadata or `modelspec.trigger_phrase`, without guessing from filenames or training tags. If no explicit metadata exists, enter the author's documented trigger words manually or select none.
6. Optionally import local wildcard libraries and tick those to include in the source menu.
7. Choose **Workflow labels**, then click **Save recipe & generate workflow** and **Open generated workflow**.
8. Choose a source, enter optional prompt text, set your switches and run normally.

Recipes are immutable and stored under your local ComfyUI user directory. Changes create a new recipe; older queued jobs retain their original bindings. Share the portable starter with other users so they can configure their own local models. Generated snapshot workflows refer to a local recipe and are not portable by themselves.

## ComfyLink phone setup

1. Save and generate the workflow on desktop.
2. FRAME 0.2.5 refreshes the paired ComfyLink backend node definitions when saving a recipe. Check the save result. If it reports a refresh failure, restart ComfyUI while idle or refresh backend node definitions before uploading.
3. Upload or update the generated workflow in the desktop ComfyLink panel.
4. Sync the workflow on your phone.
5. Use the **Prompt source** and **Selection mode** dropdowns, optional manual text, quality switches and your named LoRA switches.

If a source or mode field appears as an editable text box, refresh the phone's backend node/model definitions, then sync the workflow again. Workflow upload and node-definition refresh are separate operations; FRAME now performs the latter automatically on recipe save when the installed ComfyLink plugin supports it. This fixes new snapshot nodes appearing as text fields after a hot save. Offline, unpaired or unsupported plugins leave the desktop recipe usable and show a refresh warning instead of reporting success. No pairing permissions are changed. After changing model bindings, LoRA groups, selected libraries or workflow language, generate and sync the new workflow again.

The phone interface avoids file selectors, strength fields and trigger editing. Desktop configuration owns those details. Existing accounts and backend pairing permissions are not changed by this extension. Shared-backend execution may require a compatible ComfyLink version; see the source repository's compatibility notes.

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
ignores its number. Exclusive groups retain their single-selection rule. Both
FRAME Link and ComfyLink expose these ordinary FLOAT controls without a phone
app update. Old recipe snapshots keep their original Boolean-only contract.
Save/export and sync a new recipe after replacing a LoRA file. The PNG receipt
records the actual model and CLIP strengths used for enabled LoRAs.
