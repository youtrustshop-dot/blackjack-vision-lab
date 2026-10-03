import {getLanguage,Language,setLanguage,t} from './i18n';
export default function LanguageSelector({onChange}:{onChange:(language:Language)=>void}){
 return <label className="language-picker"><span>{t('Language')}</span><select aria-label={t('Language')} value={getLanguage()} onChange={e=>{const value=e.target.value as Language;setLanguage(value);onChange(value)}}><option value="en">English</option><option value="it">Italiano</option></select></label>;
}
