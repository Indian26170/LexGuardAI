'use client';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/store';
import { uploadDocument, getAudits, logout } from '@/lib/api';
import { io, Socket } from 'socket.io-client';
import Link from 'next/link';

interface Audit {
    _id: string;
    legalScore: number;
    scoreLabel: string;
    status: string;
    language: string;
    createdAt: string;
    document: {
        originalName: string;
        docType: string;
    };
}

export default function DashboardPage() {
    const router = useRouter();
    const { user, clearAuth } = useAuthStore();
    const [audits, setAudits] = useState<Audit[]>([]);
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState('');
    const [dragOver, setDragOver] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [filters, setFilters] = useState({
        docType: 'other',
        region: 'national',
        country: 'IN',
        language: 'en',
    });
    const fileRef = useRef<HTMLInputElement>(null);
    const socketRef = useRef<Socket | null>(null);

    useEffect(() => {
        const storedToken = localStorage.getItem('lexguard_token');
        const storedUser = localStorage.getItem('lexguard_user');
        if (!storedToken) { router.push('/login'); return; }
        if (storedUser && !user) {
            const parsed = JSON.parse(storedUser);
            useAuthStore.getState().setAuth(parsed, storedToken);
        }
        fetchAudits();
        setupSocket();
        return () => { socketRef.current?.disconnect(); };
    }, []);

    const setupSocket = () => {
        const userId = JSON.parse(localStorage.getItem('lexguard_user') || '{}')._id;
        const socket = io(process.env.NEXT_PUBLIC_API_URL!, {
            withCredentials: true,
            auth: { userId },
        });
        socketRef.current = socket;

        socket.on('connect', () => {
            console.log('Socket connected:', socket.id);
        });

        socket.on('audit:start', () => setProgress('Analysis started...'));
        socket.on('audit:progress', (data: any) => setProgress(data.message));
        socket.on('audit:complete', (data: any) => {
            setUploading(false);
            setProgress('');
            setSelectedFile(null);
            fetchAudits();
            setTimeout(() => {
                router.push(`/audit/${data.auditId}`);
            }, 800);
        });
        socket.on('audit:error', (data: any) => {
            setUploading(false);
            setProgress(data?.message || 'Analysis failed. Please try again.');
        });
    };

    const fetchAudits = async () => {
        try {
            const res = await getAudits();
            setAudits(res.data.audits);
            const storedUser = localStorage.getItem('lexguard_user');
            if (storedUser) {
                const parsed = JSON.parse(storedUser);
                parsed.auditCount = res.data.pagination.total;
                localStorage.setItem('lexguard_user', JSON.stringify(parsed));
                useAuthStore.getState().setAuth(parsed, localStorage.getItem('lexguard_token')!);
            }
        } catch { }
    };

    const handleFileSelect = (file: File) => {
        setSelectedFile(file);
        setProgress('');
    };

    const handleCheck = async () => {
        if (!selectedFile) return;
        const formData = new FormData();
        formData.append('document', selectedFile);
        formData.append('docType', filters.docType);
        formData.append('region', filters.region);
        formData.append('country', filters.country);
        formData.append('language', filters.language);
        setUploading(true);
        setProgress('Uploading document...');
        try {
            await uploadDocument(formData);
        } catch (err: any) {
            setUploading(false);
            setProgress(err.response?.data?.message || 'Upload failed.');
        }
    };

    const handleLogout = async () => {
        await logout();
        clearAuth();
        router.push('/');
    };

    const scoreColor = (score: number) =>
        score >= 71 ? 'text-emerald-400' : score >= 41 ? 'text-amber-400' : 'text-red-400';

    const scoreBg = (score: number) =>
        score >= 71 ? 'bg-emerald-500/10 border-emerald-500/20' :
            score >= 41 ? 'bg-amber-500/10 border-amber-500/20' :
                'bg-red-500/10 border-red-500/20';

    const navItems = [
        {
            icon: (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" />
                    <rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" />
                </svg>
            ),
            label: 'Dashboard', href: '/dashboard'
        },
        {
            icon: (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" />
                    <line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
                </svg>
            ),
            label: 'My Audits', href: '/dashboard'
        },
        {
            icon: (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                </svg>
            ),
            label: 'Profile', href: '/dashboard/profile'
        },
    ];

    return (
        <main className="relative min-h-screen">
            <div className="relative z-10 flex h-screen">

                {/* Sidebar */}
                <aside className="w-64 glass border-r border-white/5 flex flex-col p-5 shrink-0">
                    {/* Logo */}
                    <div className="flex items-center gap-3 mb-8 px-1">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
                            <span className="text-white font-bold text-sm">L</span>
                        </div>
                        <span className="font-bold text-base" style={{ fontFamily: 'Space Grotesk' }}>
                            LexGuard <span className="text-blue-400">AI</span>
                        </span>
                    </div>

                    {/* Nav */}
                    <nav className="flex-1 space-y-1">
                        {navItems.map((item) => (
                            <Link
                                href={item.href}
                                key={item.label}
                                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${item.label === 'Dashboard' || item.label === 'My Audits'
                                        ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                                        : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'
                                    }`}
                            >
                                {item.icon}
                                {item.label}
                            </Link>
                        ))}
                    </nav>

                    {/* Bottom user section */}
                    <div className="border-t border-white/5 pt-4 space-y-3">
                        <div className="flex items-center gap-3">
                            {/* Square avatar with rounded corners */}
                            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white text-sm font-bold shrink-0">
                                {user?.name?.[0]?.toUpperCase() || '?'}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="text-sm text-white font-medium truncate">{user?.name || 'User'}</div>
                                <div className="text-xs text-slate-500">{user?.auditCount || 0} audits run</div>
                            </div>
                        </div>
                        <button
                            onClick={handleLogout}
                            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-sm text-slate-500 hover:text-red-400 hover:bg-red-500/5 border border-white/5 hover:border-red-500/20 transition-all"
                        >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                                <polyline points="16 17 21 12 16 7" />
                                <line x1="21" y1="12" x2="9" y2="12" />
                            </svg>
                            Sign Out
                        </button>
                    </div>
                </aside>

                {/* Main */}
                <div className="flex-1 overflow-auto p-8">
                    <div className="max-w-4xl mx-auto">

                        {/* Header */}
                        <div className="mb-8 animate-fade-in">
                            <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk' }}>
                                Document Audit
                            </h1>
                            <p className="text-slate-500 text-sm mt-1">Upload a contract and click Check to get your Legal Health Score</p>
                        </div>

                        {/* Filters */}
                        <div className="glass rounded-2xl p-5 mb-5 animate-fade-in">
                            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">Document Settings</h3>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                <div>
                                    <label className="text-xs text-slate-500 mb-1.5 block">Document Type</label>
                                    <select
                                        className="input-field text-sm py-2"
                                        value={filters.docType}
                                        onChange={(e) => setFilters({ ...filters, docType: e.target.value })}
                                    >
                                        <option value="other">General</option>
                                        <option value="employment">Employment Contract</option>
                                        <option value="rental">Rental Agreement</option>
                                        <option value="nda">NDA</option>
                                        <option value="service">Service Agreement</option>
                                        <option value="trade">Trade Invoice</option>
                                        <option value="financial">Loan Agreement</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="text-xs text-slate-500 mb-1.5 block">Region</label>
                                    <select
                                        className="input-field text-sm py-2"
                                        value={filters.region}
                                        onChange={(e) => setFilters({ ...filters, region: e.target.value })}
                                    >
                                        <option value="national">National</option>
                                        <option value="international">International</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="text-xs text-slate-500 mb-1.5 block">Jurisdiction</label>
                                    <select
                                        className="input-field text-sm py-2"
                                        value={filters.country}
                                        onChange={(e) => setFilters({ ...filters, country: e.target.value })}
                                    >
                                        <option value="IN">India</option>
                                        <option value="US">USA</option>
                                        <option value="UK">UK</option>
                                        <option value="IN-US">India + USA</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="text-xs text-slate-500 mb-1.5 block">Summary Language</label>
                                    <select
                                        className="input-field text-sm py-2"
                                        value={filters.language}
                                        onChange={(e) => setFilters({ ...filters, language: e.target.value })}
                                    >
                                        <option value="en">English</option>
                                        <option value="hi">Hindi</option>
                                        <option value="pa">Punjabi</option>
                                    </select>
                                </div>
                            </div>
                        </div>

                        {/* Upload Zone */}
                        <div className="glass rounded-2xl p-8 mb-5 animate-fade-in">
                            {uploading ? (
                                /* Analyzing state */
                                <div className="flex flex-col items-center gap-4 py-4">
                                    <div className="w-12 h-12 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
                                    <div className="text-center">
                                        <p className="text-blue-400 font-medium">Analyzing Document</p>
                                        <p className="text-slate-500 text-sm mt-1">{progress}</p>
                                    </div>
                                </div>
                            ) : selectedFile ? (
                                /* File selected state */
                                <div className="flex flex-col items-center gap-5">
                                    <div className="w-full flex items-center gap-4 p-4 bg-blue-500/5 border border-blue-500/20 rounded-xl">
                                        <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center shrink-0">
                                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                                <polyline points="14 2 14 8 20 8" />
                                            </svg>
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-white text-sm font-medium truncate">{selectedFile.name}</p>
                                            <p className="text-slate-500 text-xs mt-0.5">{(selectedFile.size / 1024).toFixed(1)} KB</p>
                                        </div>
                                        <button
                                            onClick={() => { setSelectedFile(null); if (fileRef.current) fileRef.current.value = ''; }}
                                            className="text-slate-500 hover:text-red-400 transition-colors p-1"
                                        >
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                                            </svg>
                                        </button>
                                    </div>

                                    <div className="flex items-center gap-3 w-full">
                                        <button
                                            onClick={() => { setSelectedFile(null); if (fileRef.current) fileRef.current.value = ''; fileRef.current?.click(); }}
                                            className="btn-secondary flex-1 py-2.5 rounded-xl text-sm"
                                        >
                                            Change File
                                        </button>
                                        <button
                                            onClick={handleCheck}
                                            className="btn-primary flex-1 py-2.5 rounded-xl text-sm flex items-center justify-center gap-2"
                                        >
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
                                            </svg>
                                            Check Contract
                                        </button>
                                    </div>
                                </div>
                            ) : (
                                /* Empty drop zone */
                                <div
                                    className={`flex flex-col items-center gap-4 py-4 cursor-pointer transition-all rounded-xl border-2 border-dashed p-8 ${dragOver ? 'border-blue-500 bg-blue-500/5' : 'border-white/10 hover:border-white/20'
                                        }`}
                                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                                    onDragLeave={() => setDragOver(false)}
                                    onDrop={(e) => {
                                        e.preventDefault();
                                        setDragOver(false);
                                        const file = e.dataTransfer.files[0];
                                        if (file) handleFileSelect(file);
                                    }}
                                    onClick={() => fileRef.current?.click()}
                                >
                                    <div className="w-16 h-16 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-3xl animate-float">
                                        📄
                                    </div>
                                    <div className="text-center">
                                        <p className="text-white font-semibold text-lg">Drop your contract here</p>
                                        <p className="text-slate-500 text-sm mt-1">or click to browse · PDF, DOCX, TXT · max 20MB</p>
                                    </div>
                                    <div className="btn-primary px-6 py-2.5 rounded-xl text-sm">
                                        Choose File
                                    </div>
                                </div>
                            )}
                            <input
                                ref={fileRef}
                                type="file"
                                accept=".pdf,.docx,.doc,.txt"
                                className="hidden"
                                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFileSelect(f); }}
                            />
                        </div>

                        {/* Recent Audits */}
                        <div className="animate-fade-in">
                            <h2 className="text-base font-semibold text-white mb-4" style={{ fontFamily: 'Space Grotesk' }}>
                                Recent Audits
                            </h2>
                            {audits.length === 0 ? (
                                <div className="glass rounded-2xl p-8 text-center text-slate-500 text-sm">
                                    No audits yet. Upload your first contract above.
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {audits.map((audit) => (
                                        <Link href={`/audit/${audit._id}`} key={audit._id}>
                                            <div className="glass glass-hover rounded-xl p-4 flex items-center gap-4 cursor-pointer mb-2">
                                                <div className={`w-11 h-11 rounded-xl border flex items-center justify-center flex-shrink-0 ${scoreBg(audit.legalScore)}`}>
                                                    <span className={`text-base font-bold ${scoreColor(audit.legalScore)}`} style={{ fontFamily: 'Space Grotesk' }}>
                                                        {audit.status === 'processing' ? '...' : audit.legalScore || '?'}
                                                    </span>
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="text-white text-sm font-medium truncate">
                                                        {audit.document?.originalName || 'Document'}
                                                    </div>
                                                    <div className="text-slate-500 text-xs mt-0.5">
                                                        {audit.document?.docType} · {new Date(audit.createdAt).toLocaleDateString()}
                                                    </div>
                                                </div>
                                                <div className={`badge ${audit.scoreLabel === 'LOW_RISK' ? 'badge-green' :
                                                        audit.scoreLabel === 'MEDIUM_RISK' ? 'badge-yellow' : 'badge-red'
                                                    }`}>
                                                    {audit.scoreLabel?.replace('_', ' ') || audit.status}
                                                </div>
                                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                    <polyline points="9 18 15 12 9 6" />
                                                </svg>
                                            </div>
                                        </Link>
                                    ))}
                                </div>
                            )}
                        </div>

                    </div>
                </div>
            </div>
        </main>
    );
}