import { createContext,useContext,useEffect,useState,type ReactNode } from 'react';
import { Navigate,Outlet } from 'react-router-dom';
import { request } from './api/client';
export type Role='admin'|'engineer'|'qa_lead'|'viewer';
export interface User {id:string;email:string;role:Role;active:boolean}
type Action='analyze'|'upload'|'machines'|'documents'|'propose'|'approve'|'evals'|'users';
const allowed:Record<Action,Role[]>={analyze:['admin','engineer','qa_lead'],upload:['admin','engineer'],machines:['admin'],documents:['admin','engineer'],propose:['admin','engineer'],approve:['admin','qa_lead'],evals:['admin','qa_lead'],users:['admin']};
const Auth=createContext<{user:User|null;loading:boolean;login:(email:string,password:string)=>Promise<void>;logout:()=>Promise<void>;can:(a:Action)=>boolean}>(null!);
export const useAuth=()=>useContext(Auth);
export function AuthProvider({children}:{children:ReactNode}) {
 const [user,setUser]=useState<User|null>(null),[loading,setLoading]=useState(true);
 useEffect(()=>{let alive=true;const clear=()=>setUser(null);window.addEventListener('rca-auth-expired',clear);
 if(sessionStorage.getItem('rca_token')) request<User>('/api/auth/me').then(u=>alive&&setUser(u)).catch(()=>sessionStorage.removeItem('rca_token')).finally(()=>alive&&setLoading(false));else setLoading(false);
 return()=>{alive=false;window.removeEventListener('rca-auth-expired',clear);};},[]);
 const login=async(email:string,password:string)=>{const r=await request<{access_token:string;user:User}>('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password})});sessionStorage.setItem('rca_token',r.access_token);setUser(r.user);};
 const logout=async()=>{try{await request('/api/auth/logout',{method:'POST'});}finally{sessionStorage.removeItem('rca_token');setUser(null);}};
 return <Auth.Provider value={{user,loading,login,logout,can:a=>!!user&&allowed[a].includes(user.role)}}>{children}</Auth.Provider>;
}
export function Guard({action}:{action?:Action}) {const {user,loading,can}=useAuth();if(loading)return <p className="p-8">Checking session…</p>;if(!user)return <Navigate to="/login" replace/>;if(action&&!can(action))return <p role="alert" className="p-8">Your role cannot open this page.</p>;return <Outlet/>;}
