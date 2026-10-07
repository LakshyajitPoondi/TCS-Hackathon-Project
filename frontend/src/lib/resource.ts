import {useEffect,useState} from 'react';
import {request,errorMessage} from '../api/client';
export function useResource<T>(path:string,revision=0){const[data,setData]=useState<T|null>(null),[error,setError]=useState('');useEffect(()=>{let alive=true;setData(null);setError('');request<T>(path).then(r=>alive&&setData(r)).catch(e=>alive&&setError(errorMessage(e)));return()=>{alive=false;};},[path,revision]);return {data,error};}
/** Tell the sidebar (and anything else listening) that pending counts may have changed. */
export const countsChanged=()=>window.dispatchEvent(new Event('rca-counts-changed'));
export const mutation=<T,>(path:string,body:unknown,method='POST')=>request<T>(path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
