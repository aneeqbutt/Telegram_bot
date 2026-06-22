"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getArticles, getCategories } from "@/lib/api";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { ChevronLeft, ChevronRight, ExternalLink, Search } from "lucide-react";

const PAGE_SIZE = 20;

export default function ArticlesPage() {
  const [page, setPage]         = useState(0);
  const [category, setCategory] = useState("all");
  const [posted, setPosted]     = useState("all");
  const [search, setSearch]     = useState("");

  const categories = useQuery({ queryKey: ["categories"], queryFn: getCategories });
  const articles   = useQuery({
    queryKey: ["articles", page, category, posted],
    queryFn: () => getArticles({
      skip: page * PAGE_SIZE,
      limit: PAGE_SIZE,
      category: category !== "all" ? category : undefined,
      is_posted: posted === "all" ? undefined : posted === "true",
    }),
  });

  const filtered = articles.data?.filter(a =>
    !search || a.title.toLowerCase().includes(search.toLowerCase())
  ) ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Articles</h1>
        <p className="text-sm text-zinc-400 mt-1">All scraped articles from CoinTelegraph and Blockworks</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
          <Input
            placeholder="Search title..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9 w-56 bg-zinc-900 border-zinc-700 text-zinc-200 placeholder:text-zinc-500"
          />
        </div>
        <Select value={category} onValueChange={(v: string) => { setCategory(v); setPage(0); }}>
          <SelectTrigger className="w-44 bg-zinc-900 border-zinc-700 text-zinc-200">
            <SelectValue placeholder="All Categories" />
          </SelectTrigger>
          <SelectContent className="bg-zinc-900 border-zinc-700">
            <SelectItem value="all">All Categories</SelectItem>
            {categories.data?.map(c => (
              <SelectItem key={c._id} value={c.name}>{c.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={posted} onValueChange={(v: string) => { setPosted(v); setPage(0); }}>
          <SelectTrigger className="w-36 bg-zinc-900 border-zinc-700 text-zinc-200">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent className="bg-zinc-900 border-zinc-700">
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="true">Posted</SelectItem>
            <SelectItem value="false">Pending</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-zinc-800 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-400">Title</TableHead>
              <TableHead className="text-zinc-400 w-28">Category</TableHead>
              <TableHead className="text-zinc-400 w-24">Status</TableHead>
              <TableHead className="text-zinc-400 w-28">Published</TableHead>
              <TableHead className="text-zinc-400 w-10"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {articles.isLoading
              ? Array(8).fill(0).map((_, i) => (
                <TableRow key={i} className="border-zinc-800">
                  <TableCell><Skeleton className="h-4 w-full bg-zinc-800" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-20 bg-zinc-800" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16 bg-zinc-800" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-20 bg-zinc-800" /></TableCell>
                  <TableCell></TableCell>
                </TableRow>
              ))
              : filtered.map(a => (
                <TableRow key={a._id} className="border-zinc-800 hover:bg-zinc-900">
                  <TableCell className="font-medium text-zinc-200 max-w-xs">
                    <p className="truncate">{a.title}</p>
                    <p className="text-xs text-zinc-500 truncate">{a.url}</p>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs border-zinc-700 text-zinc-400">{a.category}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge className={`text-xs ${a.is_posted ? "bg-green-900/60 text-green-300" : "bg-yellow-900/60 text-yellow-300"}`}>
                      {a.is_posted ? "Posted" : "Pending"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-zinc-500">
                    {new Date(a.published_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <a href={a.url} target="_blank" rel="noreferrer">
                      <ExternalLink className="h-3.5 w-3.5 text-zinc-600 hover:text-zinc-300 transition-colors" />
                    </a>
                  </TableCell>
                </TableRow>
              ))
            }
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500">{filtered.length} articles shown</p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
            className="border-zinc-700 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="flex items-center px-3 text-sm text-zinc-400">Page {page + 1}</span>
          <Button variant="outline" size="sm" onClick={() => setPage(p => p + 1)} disabled={(articles.data?.length ?? 0) < PAGE_SIZE}
            className="border-zinc-700 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
