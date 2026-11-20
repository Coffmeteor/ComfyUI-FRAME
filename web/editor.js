import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

import { validateWorkflowInputs } from "./workflow_validation.js";

const VERSION = "0.3.7";
import { resolveLanguage, translate } from "./i18n.js";
const LANGUAGE_KEY = "FRAME.editorLanguage";
function preference() { try { return localStorage.getItem(LANGUAGE_KEY) || "auto"; } catch { return "auto"; } }
function locale() { return app.ui.settings.getSettingValue("Comfy.Locale") || document.documentElement.lang || navigator.language; }
let activeLanguage = resolveLanguage(preference(), locale());
const t = text => translate(text, activeLanguage);
function el(tag, text = "", parent = null, localize = true) {
  const node = document.createElement(tag);
  if (text) { node.textContent = localize ? t(text) : text; if (localize) node.dataset.frameI18n = text; }
  if (parent) parent.append(node);
  return node;
}
function field(parent, title, value, options = null, type = "text") {
  const label = el("label", title, parent);
  label.style.cssText = "display:inline-flex;gap:8px;align-items:center;margin:6px;flex-wrap:wrap";
  const input = el(options ? "select" : type === "textarea" ? "textarea" : "input", "", label);
  if (options) for (const choice of ["", ...options]) {
    const item = el("option", choice || "— Not configured —", input); item.value = choice;
  }
  else if (type !== "textarea") input.type = type;
  if (type === "checkbox") input.checked = !!value;
  else input.value = value ?? "";
  input.style.cssText = "max-width:450px;padding:6px";
  return input;
}
async function request(path, options = {}) {
  const response = await api.fetchApi(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || response.statusText);
  return body;
}

export async function buildMobileWorkflow(descriptor) {
  // Native constructors and serialization own graph structure and widget order.
  const sourceType = descriptor.source || "FrameSource";
  const types = [sourceType, descriptor.main, ...(descriptor.batch ? [descriptor.batch] : []), ...descriptor.groups.map(g => g.type)];
  const defs = {};
  for (const type of types) if (!LiteGraph.registered_node_types[type]) Object.assign(defs, await request("/object_info/" + encodeURIComponent(type)));
  if (Object.keys(defs).length) await app.registerNodesFromDefs(defs);
  const graph = new LiteGraph.LGraph();
  const add = (type, title, x, y) => {
    const n = LiteGraph.createNode(type);
    if (!n) throw new Error("Node registration failed: " + type);
    n.title = title; n.pos = [x, y];
    n.properties = { ...n.properties, cnr_id: "frame-nodes", ver: VERSION, aux_id:"Coffmeteor/ComfyUI-FRAME" };
    graph.add(n);
    return n;
  };
  const source = add(sourceType, descriptor.source_title || "Prompt source", 50, 50);
  const main = add(descriptor.main, descriptor.main_title || "Prompt & Quality", 50, 270);
  source.connect(0, main, main.findInputSlot("source"));
  if (descriptor.batch) {
    const batch = add(descriptor.batch, descriptor.batch_title, -410, 50);
    batch.connect(0, main, main.findInputSlot("catalog_batch"));
  }
  let previous = null;
  let groupY = 50, rowHeight = 0;
  descriptor.groups.forEach((group, index) => {
    if (index && index % 3 === 0) { groupY += rowHeight + 100; rowHeight = 0; }
    const n = add(group.type, group.title, 470 + (index % 3) * 420, groupY);
    n.size[0] = Math.max(n.size[0], 360);
    rowHeight = Math.max(rowHeight,n.size[1]);
    if (previous) previous.connect(0, n, n.findInputSlot("previous"));
    previous = n;
  });
  if (previous) previous.connect(0, main, main.findInputSlot("loras"));
  const ui = graph.serialize();
  ui.extra = { ...(ui.extra || {}), comfylink: { name: descriptor.name },
               frame: { schema: 1, snapshot: descriptor.snapshot }, ds: {scale:0.65,offset:[70,100]} };
  const { output } = await app.graphToPrompt(graph);
  validateWorkflowInputs(output, descriptor);
  return { ui, output };
}

export async function openEditor(clipType = "krea2", drafts = new Map(), previousDialog = null) {
  activeLanguage = resolveLanguage(preference(), locale());
  const state = await request("/frame-nodes/state?clip_type=" + encodeURIComponent(clipType));
  const draft = drafts.get(clipType);
  const recipe = draft?.recipe || state.recipe;
  const moss = clipType === "moss_image";
  const dialog = el("dialog");
  dialog.style.cssText = "width:min(1100px,94vw);height:86vh;background:#202126;color:#eee;border:1px solid #777;border-radius:14px;padding:24px;overflow:auto";
  document.body.append(dialog);
  const close = el("button", "Close", dialog); close.style.float = "right";
  close.onclick = () => { dialog.close(); dialog.remove(); };
  el("h2", "FRAME Recipe Setup", dialog);
  const language = field(dialog, "Editor language", preference(), ["auto", "en", "zh"]);
  for (const option of language.options) { option.dataset.frameI18n = ({auto:"Auto",en:"English",zh:"Chinese"})[option.value] || "— Not configured —"; option.textContent = t(option.dataset.frameI18n); }
  language.onchange = () => {
    if (!["auto","en","zh"].includes(language.value)) return;
    localStorage.setItem(LANGUAGE_KEY, language.value);
    activeLanguage = resolveLanguage(language.value, locale());
    for (const node of dialog.querySelectorAll("[data-frame-i18n]")) {
      if (node.firstChild?.nodeType === Node.TEXT_NODE) node.firstChild.nodeValue = t(node.dataset.frameI18n);
    }
  };
  const family = field(dialog, "Model family", clipType, ["krea2", "moss_image"]);
  family.remove(0);
  family.options[0].textContent = "Krea2";
  family.options[1].textContent = "MOSS";
  el("p", moss
    ? "Choose your MOSS models and compatible LoRAs here. In ComfyLink, pick a prompt library, a resolution, and up to four LoRAs from the stack."
    : "Configure models, LoRAs and local libraries on desktop. On your phone, use two menus plus quality and LoRA switches. Files, strengths and triggers stay on this computer.", dialog);
  el("p", "Library modes ignore manual text by default. Enable Append manual text in the source card to include it. Manual-only mode always uses your text.", dialog);
  const title = field(dialog, "Workflow name", recipe.name);
  const exportLanguage = field(dialog, "Workflow labels", recipe.language || "zh", ["en", "zh", "bilingual"]);
  for (const option of exportLanguage.options) { option.dataset.frameI18n = ({en:"English",zh:"Chinese",bilingual:"Bilingual"})[option.value] || "— Not configured —"; option.textContent = t(option.dataset.frameI18n); }
  el("p", "Export labels are saved with the recipe. Resave and sync to update phone controls. Your custom group and LoRA names are kept as entered.", dialog);
  const models = el("details", "", dialog); models.open = true;
  el("summary", "Models (first-time setup)", models);
  const modelInputs = {};
  const modelLabels = {unet:"Diffusion model",alternate_unet:"Alternate model",text_encoder:"Text encoder",vae:"VAE",upscaler:"Upscaler model",face_detector:"Face detector",seedvr_model:"SeedVR2 model",seedvr_vae:"SeedVR2 VAE"};
  for (const [key, label] of Object.entries(modelLabels)) {
    if (key in state.models) modelInputs[key] = field(models, label, recipe.models[key], state.models[key]);
  }
  const generation = el("details", "", dialog); el("summary", moss ? "MOSS sampling" : "Krea2 sampling", generation);
  const genInputs = {};
  const samplingFields = {steps: ["Steps", "number"], cfg: ["CFG", "number"], sampler: ["Sampler", "text"],
    scheduler: ["Scheduler", "text"], shift: ["Flow shift", "number"], negative_prompt: ["Negative prompt", "textarea"]};
  for (const [key, value] of Object.entries(state.generation_defaults)) {
    const [label, type] = samplingFields[key];
    genInputs[key] = field(generation, label, recipe.generation[key] ?? value, null, type);
    if (key === "cfg" || key === "shift") genInputs[key].step = "0.1";
  }
  const local = el("details", "", dialog);
  el("summary", "Local wildcard libraries", local);
  el("p", "Import UTF-8 .txt: one entry per line, or multiline entries separated by blank lines. Whole-line # comments are ignored. Nested __references__ and {A|B} expressions are literal text. Select libraries for the phone menu, then save.", local);
  const uploadLabel = el("label", "Choose a .txt file ", local);
  const upload = el("input", "", uploadLabel); upload.type="file"; upload.accept=".txt,text/plain";
  const importName = field(local,"Library name","");
  const importMode = field(local,"Import format","One entry per line",["One entry per line","Blank-line blocks (multiline)"]);
  upload.onchange=()=>{if(upload.files[0]) importName.value=upload.files[0].name.replace(/\.txt$/i,"");};
  const importButton=el("button","Import library",local);
  const importStatus=el("p","",local);
  const libraryArea=el("div","",local), libraryRows=new Map();
  function addLibrary(row, selected=false) {
    if(libraryRows.has(row.id)) { if(selected) libraryRows.get(row.id).check.checked=true; return; }
    const line=el("div","",libraryArea);
    const check=field(line,row.name+" ("+row.count+")",selected,null,"checkbox");
    libraryRows.set(row.id,{row,check});
  }
  for(const row of state.wildcards || []) addLibrary(row,(recipe.wildcards || []).some(x=>x.id===row.id));
  importButton.onclick=async()=>{
    importButton.disabled=true; importStatus.textContent=t("Importing…");
    try {
      const file=upload.files[0];
      if(!file || !file.name.toLowerCase().endsWith(".txt")) throw new Error(t("Choose a .txt file"));
      if(file.size>4*1024*1024) throw new Error(t("Maximum file size: 4 MiB"));
      const text=new TextDecoder("utf-8",{fatal:true}).decode(await file.arrayBuffer());
      const result=await request("/frame-nodes/wildcards",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:importName.value,text,mode:importMode.value==="One entry per line"?"lines":"blocks"})});
      addLibrary(result.library,true);
      importStatus.textContent=t("Imported entries: ")+result.library.count+t(". Save the recipe to add this library to the phone menu.");
    } catch(e) { importStatus.textContent=e.message; }
    finally { importButton.disabled=false; }
  };
  const groupArea = el("div", "", dialog);
  const groups = [];
  function addGroup(data = {name:"My LoRAs",exclusive:false,entries:[]}) {
    const section = el("details", "", groupArea); section.open = data.entries.length === 0;
    const summary = el("summary", moss ? "MOSS LoRA Stack" : data.name, section, moss);
    const name = moss ? null : field(section,"Group name",data.name);
    if (name) name.oninput = () => summary.textContent = name.value;
    const exclusive = moss ? null : field(section,"Allow only one active LoRA",data.exclusive,null,"checkbox");
    const group = {section,name,exclusive,rows:[]}; groups.push(group);
    if (!moss) el("button","Remove group",section).onclick = () => { groups.splice(groups.indexOf(group),1); section.remove(); };
    const rows = el("div","",section);
    function addRow(data = {}) {
      const row = el("div","",rows); row.style.cssText="border:1px solid #555;padding:10px;margin:10px 0;border-radius:8px";
      const file = field(row,"LoRA file",data.file,state.loras);
      const label = field(row,moss ? "Phone LoRA name" : "Phone switch name",data.name);
      const strength = moss ? null : field(row,"Model strength",data.strength_model ?? 1,null,"number");
      const clip = moss ? null : field(row,"CLIP strength",data.strength_clip ?? 0,null,"number");
      if (strength) strength.step="0.05";
      if (clip) clip.step="0.05";
      const mode = field(row,"Trigger mode",data.trigger_mode || "auto",["auto","manual","none"]);
      const trigger = field(row,"Manual trigger words",data.trigger || "");
      trigger.oninput = () => { mode.value="manual"; };
      const stageInputs = {};
      if (!moss) for (const [key,title] of [["base","Base sampling"],["upscale","Redraw"],["detailer","Face detail"]]) stageInputs[key] = field(row,title,(data.stages || ["base","upscale","detailer"]).includes(key),null,"checkbox");
      const detected = el("span",data.trigger_source ? t("Source: ") + data.trigger_source : "",row);
      const read = el("button","Read triggers",row);
      read.onclick = async () => {
        try { const info = await request("/frame-nodes/trigger?file=" + encodeURIComponent(file.value));
          if (info.text) { trigger.value = info.text; mode.value="auto"; }
          detected.textContent = info.text ? t("Source: ") + info.source : t("No explicit trigger metadata found. Enter triggers manually or select none.");
        } catch(e) { detected.textContent = e.message; }
      };
      file.onchange = () => { trigger.value=""; mode.value="auto"; if (!label.value) label.value=file.value.split("/").pop().replace(/\.safetensors$/i,""); read.click(); };
      const entry = {row,file,label,strength,clip,mode,trigger,stageInputs}; group.rows.push(entry);
      el("button","Remove LoRA",row).onclick = () => { group.rows.splice(group.rows.indexOf(entry),1); row.remove(); };
    }
    data.entries.forEach(addRow);
    el("button","+ Add LoRA",section).onclick = () => addRow();
  }
  if (moss) addGroup(recipe.groups[0]);
  else {
    recipe.groups.forEach(addGroup);
    el("button","+ Add group",dialog).onclick = () => addGroup();
  }
  const path = field(dialog,"Workflow save path", draft?.workflowPath ?? state.workflow_path);
  const message = el("p","",dialog);
  function readRecipe() {
    const body = {schema_version:1,mobile_controls:2,mobile_strengths:true,language:exportLanguage.value,name:title.value,models:{},generation:{clip_type:clipType},groups:[]};
    body.wildcards=[...libraryRows.values()].filter(x=>x.check.checked).map(x=>({id:x.row.id,name:x.row.name}));
    for (const [key, input] of Object.entries(modelInputs)) if (input.value) body.models[key]=input.value;
    for (const [key,input] of Object.entries(genInputs)) body.generation[key]=input.type === "number" ? Number(input.value) : input.value;
    body.groups=groups.map(g=>({name:g.name?.value ?? "MOSS LoRA Stack",exclusive:g.exclusive?.checked ?? false,entries:g.rows.map(r=>({
      name:r.label.value,file:r.file.value,strength_model:Number(r.strength?.value ?? 1),strength_clip:Number(r.clip?.value ?? 0),
      trigger_mode:r.mode.value,trigger:r.trigger.value,stages:moss ? ["base"] : Object.entries(r.stageInputs).filter(([,v])=>v.checked).map(([k])=>k)
    }))}));
    return body;
  }
  family.onchange = async () => {
    drafts.set(clipType, {recipe: readRecipe(), workflowPath: path.value});
    family.disabled = true;
    try { await openEditor(family.value, drafts, dialog); }
    catch (e) { family.value = clipType; message.textContent = e.message; }
    finally { family.disabled = false; }
  };
  const open = el("button","Open generated workflow",dialog);
  open.onclick=async()=>{
    try {
      const response=await api.getUserData("workflows/"+path.value.trim());
      if(!response.ok) throw new Error(t("Save your recipe first"));
      await app.loadGraphData(await response.json());
      dialog.close();dialog.remove();
    } catch(e) {message.textContent=e.message;}
  };
  const save = el("button","Save recipe & generate workflow",dialog);
  save.style.cssText="font-size:16px;padding:12px 20px;margin:12px";
  save.onclick = async () => {
    save.disabled=true; message.textContent=t("Saving and validating…");
    try {
      const filename = path.value.trim();
      if (!filename.endsWith(".json") || filename.startsWith("/") || filename.includes("..") || filename.includes("\\")) throw new Error(t("Enter a relative .json path inside your workflow directory"));
      const body = readRecipe();
      const result = await request("/frame-nodes/recipe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({recipe:body,workflow_path:filename})});
      const built = await buildMobileWorkflow(result.descriptor);
      const stored = await api.storeUserData("workflows/"+filename,JSON.stringify(built.ui),{overwrite:true});
      if (!stored.ok) throw new Error("Workflow save failed: "+stored.status);
      const readback = await api.getUserData("workflows/"+filename);
      if (!readback.ok || JSON.stringify(await readback.json()) !== JSON.stringify(built.ui)) throw new Error(t("Saved workflow verification failed"));
      drafts.set(clipType, {recipe: body, workflowPath: filename});
      message.textContent=result.comfylink?.status === "synced"
        ? t("Generated and saved. ComfyLink node definitions refreshed. Upload this workflow in ComfyLink, then reopen it on your phone. Previous recipes are retained.")
        : t("Generated and saved. ComfyLink node definitions were not refreshed. Restart ComfyUI while idle or refresh backend node definitions in ComfyLink before uploading and syncing this workflow. Previous recipes are retained.");
    } catch(e) { message.textContent=e.message; }
    finally { save.disabled=false; }
  };
  if (previousDialog) { previousDialog.close(); previousDialog.remove(); }
  dialog.showModal();
}

app.registerExtension({name:"FRAME.RecipeEditor",commands:[{id:"FRAME.OpenRecipeEditor",label:t("FRAME · Recipe Setup"),function:()=>openEditor()}],
  async beforeRegisterNodeDef(nodeType,nodeData) {
    if(nodeData.name!=="FrameSetup") return;
    const original=nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated=function(...args){
      original?.apply(this,args);
      this.addWidget("button",t("Configure models & LoRAs"),null,()=>openEditor(),{serialize:false});
      this.size=[360,100];
    };
  },
  menuCommands:[{path:["FRAME"],commands:["FRAME.OpenRecipeEditor"]}]});
