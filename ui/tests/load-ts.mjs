import {readFile} from 'node:fs/promises';
import ts from 'typescript';
export async function loadSource(name){
 const source=await readFile(new URL('../src/'+name,import.meta.url),'utf8');
 const {outputText}=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}});
 let text=outputText;
 for(const match of [...text.matchAll(/from ['"]\.\/([^'"]+)['"]/g)]){
  const child=await readFile(new URL('../src/'+match[1]+'.ts',import.meta.url),'utf8');
  const code=ts.transpileModule(child,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
  text=text.replace(match[0],'from "data:text/javascript;base64,'+Buffer.from(code).toString('base64')+'"');
 }
 return import('data:text/javascript;base64,'+Buffer.from(text).toString('base64'));
}
