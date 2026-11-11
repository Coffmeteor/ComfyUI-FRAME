import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source = await readFile(new URL('../web/i18n.js', import.meta.url), 'utf8');
const {resolveLanguage,translate} = await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
test('Auto follows ComfyUI locale; explicit language overrides it',()=>{
  assert.equal(resolveLanguage('auto','zh-CN'),'zh');
  assert.equal(resolveLanguage('auto','zh-TW'),'zh');
  assert.equal(resolveLanguage('auto','en'),'en');
  assert.equal(resolveLanguage('auto','fr'),'en');
  assert.equal(resolveLanguage('en','zh-CN'),'en');
  assert.equal(resolveLanguage('zh','en'),'zh');
  assert.equal(resolveLanguage('auto',undefined),'en');
});
test('English labels remain English and Chinese labels translate',()=>{
  assert.equal(translate('Workflow labels','en'),'Workflow labels');
  assert.equal(translate('Workflow labels','zh'),'工作流标签语言');
  assert.equal(translate('Save recipe & generate workflow','zh'),'保存配方并生成手机工作流');
  assert.equal(translate('Custom name','zh'),'Custom name');
});
