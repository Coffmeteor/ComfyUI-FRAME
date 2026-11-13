import test from 'node:test';
import assert from 'node:assert/strict';
import {validateWorkflowInputs} from '../web/workflow_validation.js';
const descriptor={source:'Sources',main:'Generate',batch:'Batch',groups:[{type:'Loras'}],mobile_strengths:true};
const selection={batch_count:2,catalog_selection:'Fixed prompt IDs',catalog:'library',prompt_format:'prompt_krea2',prompt_ids:'1,2'};
test('export accepts dedicated batch and backward-compatible inline controls',()=>{
 assert.doesNotThrow(()=>validateWorkflowInputs({
  1:{class_type:'Sources',inputs:{'Prompt source':'Manual prompt','Selection mode':'Reuse current',append:false}},
  2:{class_type:'Generate',inputs:{source:['1',0],catalog_batch:['3',0],text:'',...selection,replay_code:'',prompt_batch:'',landscape:false}},
  3:{class_type:'Batch',inputs:selection},
  4:{class_type:'Loras',inputs:{enabled:false,strength:0.8}},
 },descriptor));
});
test('export still rejects invalid counts and unexpected scalar controls',()=>{
 for(const count of [0,11,1.5,'2']) assert.throws(()=>validateWorkflowInputs({1:{class_type:'Batch',inputs:{batch_count:count}}},descriptor));
 assert.throws(()=>validateWorkflowInputs({1:{class_type:'Generate',inputs:{unknown_number:2}}},descriptor));
 assert.throws(()=>validateWorkflowInputs({1:{class_type:'Batch',inputs:{catalog:'unknown'}}},descriptor));
});
