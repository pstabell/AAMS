"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

const EyeIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
);

const EyeOffIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
    <line x1="1" y1="1" x2="23" y2="23"/>
  </svg>
);

// Shield logo SVG
const ShieldLogo = () => (
  <svg width="64" height="72" viewBox="0 0 64 72" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M32 0L0 12v24c0 20 14 34 32 36 18-2 32-16 32-36V12L32 0z" fill="#1a1a2e"/>
    <path d="M32 4L4 14v22c0 18 12 30 28 32 16-2 28-14 28-32V14L32 4z" fill="#16213e"/>
    <path d="M32 8L8 17v19c0 16 10 27 24 29 14-2 24-13 24-29V17L32 8z" fill="#1a1a2e" stroke="#c8a84e" strokeWidth="1.5"/>
    <text x="32" y="48" textAnchor="middle" fill="#c8a84e" fontSize="32" fontWeight="bold" fontFamily="serif">$</text>
  </svg>
);

type TabType = "login" | "trial" | "agency";

export default function LoginPage() {
  const router = useRouter();
  const { login, loading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("login");

  // Agency signup fields
  const [agencyName, setAgencyName] = useState("");
  const [yourName, setYourName] = useState("");
  const [agencyEmail, setAgencyEmail] = useState("");
  const [agencyPassword, setAgencyPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [agreeTerms, setAgreeTerms] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    const result = await login(email, password);
    if (result.error) {
      setError(result.error);
      return;
    }
    router.push("/dashboard");
  };

  const tabStyle = (tab: TabType) =>
    `px-4 py-2 text-sm font-medium border-b-2 transition cursor-pointer ${
      activeTab === tab
        ? "text-orange-500 border-orange-500"
        : "text-slate-500 border-transparent hover:text-slate-700"
    }`;

  const inputStyle = "w-full rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-orange-400 focus:ring-2 focus:ring-orange-100 placeholder:text-slate-400";
  const orangeBtn = "flex w-full items-center justify-center rounded-lg bg-orange-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-orange-600 disabled:cursor-not-allowed disabled:opacity-60";
  const outlineBtn = "flex w-full items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-600 transition hover:bg-slate-50";

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-slate-50 to-white">
      {/* Main content */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-12">
        <div className="w-full max-w-lg">
          {/* Logo & Title */}
          <div className="flex items-center gap-4 mb-8">
            <ShieldLogo />
            <h1 className="text-3xl font-bold text-slate-800 leading-tight">
              Agent Management System
            </h1>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 border-b border-slate-200 mb-8">
            <button type="button" onClick={() => setActiveTab("login")} className={tabStyle("login")}>
              Login
            </button>
            <button type="button" onClick={() => setActiveTab("trial")} className={tabStyle("trial")}>
              Start Free Trial
            </button>
            <button type="button" onClick={() => setActiveTab("agency")} className={tabStyle("agency")}>
              Agency Signup
            </button>
          </div>

          {/* Login Tab */}
          {activeTab === "login" && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-slate-800">Login to Your Account</h2>

              <form className="space-y-5" onSubmit={handleSubmit}>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600" htmlFor="email">Email</label>
                  <input id="email" type="email" autoComplete="email" className={inputStyle}
                    value={email} onChange={(e) => setEmail(e.target.value)} required />
                </div>

                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600" htmlFor="password">Password</label>
                  <div className="relative">
                    <input id="password" type={showPassword ? "text" : "password"} autoComplete="current-password"
                      className={inputStyle} value={password} onChange={(e) => setPassword(e.target.value)} required />
                    <button type="button" onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600">
                      {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                    </button>
                  </div>
                </div>

                {error && (
                  <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                    {error}
                  </div>
                )}

                <button type="submit" className={orangeBtn} disabled={loading}>
                  {loading ? "Signing in..." : "Login"}
                </button>
              </form>

              <div className="text-center">
                <Link className={outlineBtn} href="/forgot-password">
                  Forgot Password?
                </Link>
              </div>
            </div>
          )}

          {/* Free Trial Tab */}
          {activeTab === "trial" && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-slate-800">Subscribe to Agent Management System</h2>
              <p className="text-sm text-slate-500">Unlock all features of Agent Management System</p>

              <div className="space-y-2">
                {[
                  "Unlimited Policy Tracking",
                  "Advanced Reporting & Analytics",
                  "Multi-User Collaboration",
                  "Automated Reconciliation",
                  "Excel Import/Export",
                  "Priority Support",
                ].map((feature) => (
                  <div key={feature} className="flex items-center gap-2">
                    <span className="text-green-500 text-lg">✅</span>
                    <span className="text-sm font-medium text-slate-700">{feature}</span>
                  </div>
                ))}
              </div>

              <h3 className="text-2xl font-bold text-slate-800 mt-6">Start Your 14-Day Free Trial</h3>
              <p className="text-slate-500 text-sm">Then $19.99/month</p>
              <p className="text-slate-400 text-xs">No charge for 14 days. Cancel anytime. Secure payment via Stripe.</p>

              <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); router.push("/signup"); }}>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600">Enter your email to subscribe:</label>
                  <input type="email" autoComplete="email" placeholder="you@agency.com" className={inputStyle} required />
                </div>

                <button type="submit" className={orangeBtn}>
                  🚀 Start Free Trial
                </button>
              </form>
            </div>
          )}

          {/* Agency Signup Tab */}
          {activeTab === "agency" && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-slate-800">🏢 Start Your Agency Account</h2>
              <p className="text-sm text-slate-500">Create an agency account to manage your team of agents</p>

              <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); router.push("/signup"); }}>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600">Agency Name*</label>
                  <input type="text" placeholder="e.g. ABC Insurance Agency" className={inputStyle}
                    value={agencyName} onChange={(e) => setAgencyName(e.target.value)} required />
                </div>

                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600">Your Name*</label>
                  <input type="text" placeholder="e.g. John Smith" className={inputStyle}
                    value={yourName} onChange={(e) => setYourName(e.target.value)} required />
                </div>

                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600">Email*</label>
                  <input type="email" placeholder="you@youragency.com" className={inputStyle}
                    value={agencyEmail} onChange={(e) => setAgencyEmail(e.target.value)} required />
                </div>

                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600">Password*</label>
                  <div className="relative">
                    <input type={showPassword ? "text" : "password"} className={inputStyle}
                      value={agencyPassword} onChange={(e) => setAgencyPassword(e.target.value)} required />
                    <button type="button" onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600">
                      {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                    </button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600">Confirm Password*</label>
                  <div className="relative">
                    <input type={showConfirmPassword ? "text" : "password"} className={inputStyle}
                      value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
                    <button type="button" onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600">
                      {showConfirmPassword ? <EyeOffIcon /> : <EyeIcon />}
                    </button>
                  </div>
                  <p className="text-xs text-slate-400">Password must be at least 8 characters</p>
                </div>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" className="rounded border-slate-300" checked={agreeTerms}
                    onChange={(e) => setAgreeTerms(e.target.checked)} required />
                  <span className="text-sm text-slate-600">
                    I agree to the <Link href="/terms" className="text-orange-500 hover:underline">Terms of Service</Link> and <Link href="/privacy" className="text-orange-500 hover:underline">Privacy Policy</Link>
                  </span>
                </label>

                <button type="submit" className={orangeBtn}>
                  Create Agency Account
                </button>
              </form>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <footer className="py-6 text-center text-xs text-slate-400">
        <div className="flex items-center justify-center gap-2">
          <Link href="/terms" className="hover:text-slate-600">Terms of Service</Link>
          <span>•</span>
          <Link href="/privacy" className="hover:text-slate-600">Privacy Policy</Link>
        </div>
        <p className="mt-2">© 2025 Metro Point Technology LLC. All rights reserved.</p>
        <p className="mt-1">Agent Management System™ is a product of Metro Point Technology LLC.</p>
      </footer>
    </div>
  );
}
