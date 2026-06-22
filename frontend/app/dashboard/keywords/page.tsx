"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getKeywords, createKeyword, deleteKeyword, getCategories } from "@/lib/api";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, Trash2, Search } from "lucide-react";
import { toast } from "sonner";

const CATEGORY_COLORS: Record<string, string> = {
  Bitcoin:    "bg-orange-900/60 text-orange-300",
  Ethereum:   "bg-blue-900/60 text-blue-300",
  DeFi:       "bg-purple-900/60 text-purple-300",
  Regulation: "bg-red-900/60 text-red-300",
  NFT:        "bg-pink-900/60 text-pink-300",
};

export default function KeywordsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [filterCat, setFilterCat] = useState("all");
  const [search, setSearch] = useState("");
  const [form, setForm] = useState({ word: "", category_name: "", weight: 1 });

  const categories = useQuery({ queryKey: ["categories"], queryFn: getCategories });
  const keywords   = useQuery({ queryKey: ["keywords", filterCat], queryFn: () => getKeywords(filterCat !== "all" ? filterCat : undefined) });

  const add = useMutation({
    mutationFn: createKeyword,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["keywords"] }); setOpen(false); setForm({ word: "", category_name: "", weight: 1 }); toast.success("Keyword added — classifier reloaded"); },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: deleteKeyword,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["keywords"] }); toast.success("Keyword deleted"); },
  });

  const filtered = keywords.data?.filter(k =>
    !search || k.word.toLowerCase().includes(search.toLowerCase())
  ) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Keywords</h1>
          <p className="text-sm text-zinc-400 mt-1">Keywords used to classify articles into categories</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2 bg-blue-600 hover:bg-blue-500"><Plus className="h-4 w-4" /> Add Keyword</Button>
          </DialogTrigger>
          <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100">
            <DialogHeader><DialogTitle>Add New Keyword</DialogTitle></DialogHeader>
            <div className="space-y-4 mt-2">
              <div className="space-y-1.5">
                <Label className="text-zinc-400">Keyword</Label>
                <Input value={form.word} onChange={e => setForm(f => ({ ...f, word: e.target.value }))}
                  placeholder="e.g. solana" className="bg-zinc-800 border-zinc-700 text-zinc-100" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400">Category</Label>
                <Select value={form.category_name} onValueChange={v => setForm(f => ({ ...f, category_name: v }))}>
                  <SelectTrigger className="bg-zinc-800 border-zinc-700 text-zinc-200">
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-700">
                    {categories.data?.map(c => <SelectItem key={c._id} value={c.name}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={() => add.mutate(form)} disabled={add.isPending || !form.word || !form.category_name}
                className="w-full bg-blue-600 hover:bg-blue-500">
                {add.isPending ? "Adding..." : "Add Keyword"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
          <Input placeholder="Search keyword..." value={search} onChange={e => setSearch(e.target.value)}
            className="pl-9 w-48 bg-zinc-900 border-zinc-700 text-zinc-200 placeholder:text-zinc-500" />
        </div>
        <Select value={filterCat} onValueChange={(v: string) => setFilterCat(v)}>
          <SelectTrigger className="w-44 bg-zinc-900 border-zinc-700 text-zinc-200">
            <SelectValue placeholder="All Categories" />
          </SelectTrigger>
          <SelectContent className="bg-zinc-900 border-zinc-700">
            <SelectItem value="all">All Categories</SelectItem>
            {categories.data?.map(c => <SelectItem key={c._id} value={c.name}>{c.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Badge variant="outline" className="border-zinc-700 text-zinc-400 self-center">
          {filtered.length} keywords
        </Badge>
      </div>

      <div className="rounded-lg border border-zinc-800 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-400">Keyword</TableHead>
              <TableHead className="text-zinc-400">Category</TableHead>
              <TableHead className="text-zinc-400 w-20">Weight</TableHead>
              <TableHead className="text-zinc-400 w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {keywords.isLoading
              ? Array(8).fill(0).map((_, i) => (
                <TableRow key={i} className="border-zinc-800">
                  {Array(4).fill(0).map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full bg-zinc-800" /></TableCell>)}
                </TableRow>
              ))
              : filtered.map(k => (
                <TableRow key={k._id} className="border-zinc-800 hover:bg-zinc-900">
                  <TableCell className="font-mono text-zinc-200">{k.word}</TableCell>
                  <TableCell>
                    <Badge className={`text-xs ${CATEGORY_COLORS[k.category_name] ?? "bg-zinc-800 text-zinc-400"}`}>
                      {k.category_name}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-zinc-400">{k.weight}</TableCell>
                  <TableCell>
                    <button onClick={() => remove.mutate(k._id)} className="text-zinc-600 hover:text-red-400 transition-colors">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </TableCell>
                </TableRow>
              ))
            }
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
