"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Newspaper, Globe, Tag, Hash, Radio, Send
} from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard",            label: "Overview",    icon: LayoutDashboard },
  { href: "/dashboard/articles",   label: "Articles",    icon: Newspaper },
  { href: "/dashboard/sources",    label: "Sources",     icon: Globe },
  { href: "/dashboard/categories", label: "Categories",  icon: Tag },
  { href: "/dashboard/keywords",   label: "Keywords",    icon: Hash },
  { href: "/dashboard/channels",   label: "Channels",    icon: Radio },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 border-r border-zinc-800 bg-zinc-900 flex flex-col">
        <div className="flex items-center gap-2 px-5 py-5 border-b border-zinc-800">
          <Send className="h-5 w-5 text-blue-400" />
          <span className="font-semibold text-sm tracking-wide text-zinc-100">CryptoBot Admin</span>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = path === href || (href !== "/dashboard" && path.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                  active
                    ? "bg-blue-600 text-white"
                    : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="px-4 py-3 border-t border-zinc-800">
          <p className="text-xs text-zinc-500">FastAPI → localhost:8000</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-zinc-950">
        <div className="max-w-6xl mx-auto px-6 py-8">
          {children}
        </div>
      </main>
    </div>
  );
}
