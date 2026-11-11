import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const VERSION = "0.2.1";
function el(tag, text = "", parent = null) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (parent) parent.append(node);
  return node;
}
function field(parent, title, value, options = null, type = "text") {
  const label = el("label", title + " ", parent);
  label.style.cssText = "display:inline-flex;gap:8px;align-items:center;margin:6px;flex-wrap:wrap";
  const input = el(options ? "select" : "input", "", label);
  if (options) for (const choice of ["", ...options]) {
    const item = el("option", choice || "— 未设置 —", input); item.value = choice;
  }
  else input.type = type;
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
  const types = [sourceType, descriptor.main, ...descriptor.groups.map(g => g.type)];
  const defs = {};
  for (const type of types) if (!LiteGraph.registered_node_types[type]) Object.assign(defs, await request("/object_info/" + encodeURIComponent(type)));
  if (Object.keys(defs).length) await app.registerNodesFromDefs(defs);
  const graph = new LiteGraph.LGraph();
  const add = (type, title, x, y) => {
    const n = LiteGraph.createNode(type);
    if (!n) throw new Error("Node registration failed: " + type);
    n.title = title; n.pos = [x, y];
    n.properties = { ...n.properties, cnr_id: "frame-nodes", ver: VERSION };
    graph.add(n);
    return n;
  };
  const source = add(sourceType, "提示词来源", 50, 50);
  const main = add(descriptor.main, "提示词与画质", 50, 270);
  source.connect(0, main, main.findInputSlot("source"));
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
  for (const node of Object.values(output)) for (const [key, value] of Object.entries(node.inputs)) {
    if (Array.isArray(value)) continue;
    if (key === "text" && typeof value === "string") continue;
    if (node.class_type === descriptor.source && ["提示词来源","抽词方式"].includes(key) && typeof value === "string") continue;
    if (typeof value !== "boolean") throw new Error("Unexpected phone widget: " + key);
  }
  return { ui, output };
}

export async function openEditor() {
  const state = await request("/frame-nodes/state");
  const recipe = structuredClone(state.recipe);
  const dialog = el("dialog");
  dialog.style.cssText = "width:min(1100px,94vw);height:86vh;background:#202126;color:#eee;border:1px solid #777;border-radius:14px;padding:24px;overflow:auto";
  document.body.append(dialog);
  const close = el("button", "关闭", dialog); close.style.float = "right";
  close.onclick = () => { dialog.close(); dialog.remove(); };
  el("h2", "FRAME 配方设置", dialog);
  el("p", "在电脑选模型、LoRA 和本地词库。手机用两个菜单选择来源及抽词方式，画质和 LoRA 仍用开关。文件、强度和触发词保存在这台电脑。", dialog);
  const title = field(dialog, "工作流名称", recipe.name);
  const models = el("details", "", dialog); models.open = true;
  el("summary", "模型设置（首次使用）", models);
  const modelInputs = {};
  const modelLabels = {unet:"主模型",alternate_unet:"备用模型",text_encoder:"文本编码器",vae:"VAE",upscaler:"图像放大模型",face_detector:"面部检测模型",seedvr_model:"SeedVR2 模型",seedvr_vae:"SeedVR2 VAE"};
  for (const [key, label] of Object.entries(modelLabels)) modelInputs[key] = field(models, label, recipe.models[key], state.models[key]);
  const generation = el("details", "", dialog); el("summary", "Krea2 采样设置", generation);
  const genInputs = {};
  for (const [key, label, value] of [["steps","步数",8],["cfg","CFG",1]]) genInputs[key] = field(generation,label,recipe.generation[key] ?? value,null,"number");
  genInputs.sampler = field(generation,"采样器",recipe.generation.sampler || "euler_ancestral");
  genInputs.scheduler = field(generation,"调度器",recipe.generation.scheduler || "beta");
  const local = el("details", "", dialog);
  el("summary", "本地 wildcard 词库", local);
  el("p", "导入 UTF-8 .txt：每行一条，或用空行分隔多行条目。忽略 # 开头的注释；不执行嵌套 __引用__ 或 {A|B} 表达式。勾选要放进手机来源菜单的词库，再保存配方。", local);
  const uploadLabel = el("label", "选择 .txt 文件 ", local);
  const upload = el("input", "", uploadLabel); upload.type="file"; upload.accept=".txt,text/plain";
  const importName = field(local,"词库名称","");
  const importMode = field(local,"文件格式","每行一条",["每行一条","空行分段（多行条目）"]);
  upload.onchange=()=>{if(upload.files[0]) importName.value=upload.files[0].name.replace(/\.txt$/i,"");};
  const importButton=el("button","导入词库",local);
  const importStatus=el("p","",local);
  const libraryArea=el("div","",local), libraryRows=new Map();
  function addLibrary(row, selected=false) {
    if(libraryRows.has(row.id)) { if(selected) libraryRows.get(row.id).check.checked=true; return; }
    const line=el("div","",libraryArea);
    const check=field(line,row.name+"（"+row.count+" 条）",selected,null,"checkbox");
    libraryRows.set(row.id,{row,check});
  }
  for(const row of state.wildcards || []) addLibrary(row,(recipe.wildcards || []).some(x=>x.id===row.id));
  importButton.onclick=async()=>{
    importButton.disabled=true; importStatus.textContent="正在导入…";
    try {
      const file=upload.files[0];
      if(!file || !file.name.toLowerCase().endsWith(".txt")) throw new Error("请选择 .txt 文件");
      if(file.size>4*1024*1024) throw new Error("文件最多 4 MiB");
      const text=new TextDecoder("utf-8",{fatal:true}).decode(await file.arrayBuffer());
      const result=await request("/frame-nodes/wildcards",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:importName.value,text,mode:importMode.value==="每行一条"?"lines":"blocks"})});
      addLibrary(result.library,true);
      importStatus.textContent="已导入 "+result.library.count+" 条。保存下方配方后，会出现在手机来源菜单。";
    } catch(e) { importStatus.textContent=e.message; }
    finally { importButton.disabled=false; }
  };
  const groupArea = el("div", "", dialog);
  const groups = [];
  function addGroup(data = {name:"我的 LoRA",exclusive:false,entries:[]}) {
    const section = el("details", "", groupArea); section.open = data.entries.length === 0;
    const summary = el("summary", data.name, section);
    const name = field(section,"分组名称",data.name); name.oninput = () => summary.textContent = name.value;
    const exclusive = field(section,"一次只允许开启一个",data.exclusive,null,"checkbox");
    const remove = el("button","删除分组",section);
    const group = {section,name,exclusive,rows:[]}; groups.push(group);
    remove.onclick = () => { groups.splice(groups.indexOf(group),1); section.remove(); };
    const rows = el("div","",section);
    function addRow(data = {}) {
      const row = el("div","",rows); row.style.cssText="border:1px solid #555;padding:10px;margin:10px 0;border-radius:8px";
      const file = field(row,"LoRA 文件",data.file,state.loras);
      const label = field(row,"手机显示名称",data.name);
      const strength = field(row,"模型强度",data.strength_model ?? 1,null,"number"); strength.step="0.05";
      const clip = field(row,"CLIP 强度",data.strength_clip ?? 0,null,"number"); clip.step="0.05";
      const mode = field(row,"触发词",data.trigger_mode || "auto",["auto","manual","none"]);
      const trigger = field(row,"手动触发词",data.trigger || "");
      trigger.oninput = () => { mode.value="manual"; };
      const stageInputs = {};
      for (const [key,title] of [["base","主采样"],["upscale","重绘"],["detailer","面部细修"]]) stageInputs[key] = field(row,title,(data.stages || ["base","upscale","detailer"]).includes(key),null,"checkbox");
      const detected = el("span",data.trigger_source ? "来源：" + data.trigger_source : "",row);
      const read = el("button","读取触发词",row);
      read.onclick = async () => {
        try { const info = await request("/frame-nodes/trigger?file=" + encodeURIComponent(file.value));
          if (info.text) { trigger.value = info.text; mode.value="auto"; }
          detected.textContent = info.text ? "来源：" + info.source : "未找到明确触发词；请手动填写或选择 none。";
        } catch(e) { detected.textContent = e.message; }
      };
      file.onchange = () => { trigger.value=""; mode.value="auto"; if (!label.value) label.value=file.value.split("/").pop().replace(/\.safetensors$/i,""); read.click(); };
      const entry = {row,file,label,strength,clip,mode,trigger,stageInputs}; group.rows.push(entry);
      el("button","删除 LoRA",row).onclick = () => { group.rows.splice(group.rows.indexOf(entry),1); row.remove(); };
    }
    data.entries.forEach(addRow);
    el("button","＋ 添加 LoRA",section).onclick = () => addRow();
  }
  recipe.groups.forEach(addGroup);
  el("button","＋ 添加分组",dialog).onclick = () => addGroup();
  const path = field(dialog,"保存到工作流列表", state.workflow_path);
  const message = el("p","",dialog);
  const save = el("button","保存配方并生成手机工作流",dialog);
  save.style.cssText="font-size:16px;padding:12px 20px;margin:12px";
  save.onclick = async () => {
    save.disabled=true; message.textContent="正在保存和验证…";
    try {
      const filename = path.value.trim();
      if (!filename.endsWith(".json") || filename.startsWith("/") || filename.includes("..") || filename.includes("\\")) throw new Error("请填写工作流目录内的相对 .json 文件名");
      const body = {schema_version:1,name:title.value,models:{},generation:{clip_type:"krea2"},groups:[]};
      body.wildcards=[...libraryRows.values()].filter(x=>x.check.checked).map(x=>({id:x.row.id,name:x.row.name}));
      for (const [key, input] of Object.entries(modelInputs)) if (input.value) body.models[key]=input.value;
      for (const [key,input] of Object.entries(genInputs)) body.generation[key]=["steps","cfg"].includes(key) ? Number(input.value) : input.value;
      body.groups=groups.map(g=>({name:g.name.value,exclusive:g.exclusive.checked,entries:g.rows.map(r=>({
        name:r.label.value,file:r.file.value,strength_model:Number(r.strength.value),strength_clip:Number(r.clip.value),
        trigger_mode:r.mode.value,trigger:r.trigger.value,stages:Object.entries(r.stageInputs).filter(([,v])=>v.checked).map(([k])=>k)
      }))}));
      const result = await request("/frame-nodes/recipe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({recipe:body,workflow_path:filename})});
      const built = await buildMobileWorkflow(result.descriptor);
      const stored = await api.storeUserData("workflows/"+filename,JSON.stringify(built.ui),{overwrite:true});
      if (!stored.ok) throw new Error("保存工作流失败："+stored.status);
      const readback = await api.getUserData("workflows/"+filename);
      if (!readback.ok || JSON.stringify(await readback.json()) !== JSON.stringify(built.ui)) throw new Error("工作流保存后校验失败");
      message.textContent="已生成并保存。请在队列空闲时重启 ComfyUI，再在 ComfyLink 上传此工作流并手机同步。旧配方仍保留。";
    } catch(e) { message.textContent=e.message; }
    finally { save.disabled=false; }
  };
  dialog.showModal();
}

app.registerExtension({name:"FRAME.RecipeEditor",commands:[{id:"FRAME.OpenRecipeEditor",label:"FRAME · 配方设置",function:openEditor}],
  menuCommands:[{path:["FRAME"],commands:["FRAME.OpenRecipeEditor"]}]});
