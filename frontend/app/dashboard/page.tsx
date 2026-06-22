"use client";
import { useQuery } from "@tanstack/react-query";
import { getArticles, getSources, getCategories, getKeywords } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Newspaper, Globe, Tag, Hash, Play, CheckCircle, Clock } from "lucide-react";
import { toast } from "sonner";

export default function DashboardPage() {
  const articles = useQuery({ queryKey: ["articles"], queryFn: () => getArticles({ limit: 100 }) });
  const sources   = useQuery({ queryKey: ["sources"],   queryFn: getSources });
  const categories= useQuery({ queryKey: ["categories"],queryFn: getCategories });
  const keywords  = useQuery({ queryKey: ["keywords"],  queryFn: () => getKeywords() });

  const posted    = articles.data?.filter(a => a.is_posted).length ?? 0;
  const pending   = articles.data?.filter(a => !a.is_posted).length ?? 0;
  const total     = articles.data?.length ?? 0;

  const catCounts: Record<string, number> = {};
  articles.data?.forEach(a => {
    catCounts[a.category] = (catCounts[a.category] ?? 0) + 1;
  });

  async function runNow() {
    try {
      const res = await fetch("http://localhost:8000/api/v1/admin/run-now", { method: "POST" });
      if (res.ok) toast.success("Pipeline triggered — check logs");
      else toast.error("Failed to trigger pipeline");
    } catch {
      toast.error("Could not reach FastAPI server");
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Overview</h1>
          <p className="text-sm text-zinc-400 mt-1">Telegram News Bot — Admin Dashboard</p>
        </div>
        <Button onClick={runNow} className="gap-2 bg-blue-600 hover:bg-blue-500">
          <Play className="h-4 w-4" /> Run Now
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={<Newspaper className="h-5 w-5 text-blue-400" />} label="Total Articles" value={total} loading={articles.isLoading} />
        <StatCard icon={<CheckCircle className="h-5 w-5 text-green-400" />} label="Posted" value={posted} loading={articles.isLoading} />
        <StatCard icon={<Clock className="h-5 w-5 text-yellow-400" />} label="Pending" value={pending} loading={articles.isLoading} />
        <StatCard icon={<Globe className="h-5 w-5 text-purple-400" />} label="Sources" value={sources.data?.length ?? 0} loading={sources.isLoading} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Articles by category */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-zinc-300 flex items-center gap-2">
              <Tag className="h-4 w-4 text-blue-400" /> Articles by Category
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {articles.isLoading
              ? Array(5).fill(0).map((_, i) => <Skeleton key={i} className="h-6 w-full bg-zinc-800" />)
              : Object.entries(catCounts).sort((a, b) => b[1] - a[1]).map(([cat, count]) => (
                <div key={cat} className="flex items-center justify-between">
                  <span className="text-sm text-zinc-400">{cat}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-32 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-blue-500"
                        style={{ width: `${(count / total) * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium text-zinc-300 w-6 text-right">{count}</span>
                  </div>
                </div>
              ))
            }
          </CardContent>
        </Card>

        {/* Quick stats */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-zinc-300 flex items-center gap-2">
              <Hash className="h-4 w-4 text-blue-400" /> System Status
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {[
              { label: "Active Sources",    value: sources.data?.filter(s => s.is_active).length,    total: sources.data?.length,    loading: sources.isLoading },
              { label: "Active Categories", value: categories.data?.filter(c => c.is_active).length, total: categories.data?.length, loading: categories.isLoading },
              { label: "Keywords Loaded",   value: keywords.data?.length ?? 0,                            total: keywords.data?.length ?? 0,   loading: keywords.isLoading },
            ].map(({ label, value, total: t, loading }) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-sm text-zinc-400">{label}</span>
                {loading
                  ? <Skeleton className="h-5 w-12 bg-zinc-800" />
                  : <Badge variant="secondary" className="bg-zinc-800 text-zinc-300">{value}{t !== value ? ` / ${t}` : ""}</Badge>
                }
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Recent articles */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-sm font-semibold text-zinc-300">Recent Articles</CardTitle>
        </CardHeader>
        <CardContent>
          {articles.isLoading
            ? Array(5).fill(0).map((_, i) => <Skeleton key={i} className="h-10 w-full bg-zinc-800 mb-2" />)
            : articles.data?.slice(0, 8).map(a => (
              <div key={a._id} className="flex items-center justify-between py-3 border-b border-zinc-800 last:border-0">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-200 truncate">{a.title}</p>
                  <p className="text-xs text-zinc-500 mt-0.5">{new Date(a.published_at).toLocaleDateString()}</p>
                </div>
                <div className="flex items-center gap-2 ml-4 shrink-0">
                  <Badge className="text-xs bg-zinc-800 text-zinc-400 border-zinc-700">{a.category}</Badge>
                  <Badge className={`text-xs ${a.is_posted ? "bg-green-900 text-green-300" : "bg-yellow-900 text-yellow-300"}`}>
                    {a.is_posted ? "Posted" : "Pending"}
                  </Badge>
                </div>
              </div>
            ))
          }
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({ icon, label, value, loading }: { icon: React.ReactNode; label: string; value: number; loading: boolean }) {
  return (
    <Card className="bg-zinc-900 border-zinc-800">
      <CardContent className="pt-5">
        <div className="flex items-center justify-between mb-3">
          {icon}
        </div>
        {loading
          ? <Skeleton className="h-8 w-16 bg-zinc-800" />
          : <p className="text-3xl font-bold text-zinc-100">{value}</p>
        }
        <p className="text-xs text-zinc-500 mt-1">{label}</p>
      </CardContent>
    </Card>
  );
}
