import {Children,cloneElement,isValidElement,ReactNode} from 'react';
import {t} from './i18n';
/** Translate legacy rendered labels while preserving state and event handlers. */
export function localize<T extends ReactNode>(node:T):T{
 if(typeof node==='string')return t(node) as T;
 if(Array.isArray(node))return node.map(localize) as unknown as T;
 if(!isValidElement<Record<string,unknown>>(node))return node;
 const props:Record<string,unknown>={};
 for(const key of ['title','aria-label','alt','placeholder'])if(typeof node.props[key]==='string')props[key]=t(node.props[key] as string);
 const rawData=['pre','code'].includes(String(node.type))&&typeof node.props.children==='string'&&/^[\s]*[\[{]/.test(node.props.children);
 if('children' in node.props&&!rawData)props.children=Children.map(node.props.children as ReactNode,localize);
 return cloneElement(node,props) as T;
}
