// Validate generated mobile controls without assuming that every scalar is a switch.
export function validateWorkflowInputs(output, descriptor) {
  for (const node of Object.values(output)) for (const [key, value] of Object.entries(node.inputs)) {
    if (Array.isArray(value)) continue;
    if (key === "text" && typeof value === "string") continue;
    if (node.class_type === descriptor.source && (descriptor.source_fields || ["Prompt source", "Selection mode"]).includes(key) && typeof value === "string") continue;
    if (node.class_type === descriptor.main || node.class_type === descriptor.batch) {
      if (key === "batch_count" && Number.isInteger(value) && value >= 1 && value <= 10) continue;
      if (key === "catalog_selection" && ["Workflow source", "Random IDs each run", "Fixed prompt IDs"].includes(value)) continue;
      if (key === "catalog" && ["library", "rewrite"].includes(value)) continue;
      if (["prompt_format", "prompt_ids"].includes(key) && typeof value === "string") continue;
      if (node.class_type === descriptor.main && ["replay_code", "prompt_batch"].includes(key) && typeof value === "string") continue;
    }
    if (descriptor.mobile_strengths && descriptor.groups.some(g => g.type === node.class_type) && typeof value === "number" && Number.isFinite(value)) continue;
    if (typeof value !== "boolean") throw new Error("Unexpected phone widget: " + key);
  }
}
