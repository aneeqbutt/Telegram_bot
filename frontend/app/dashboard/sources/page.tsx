"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSources, createSource, updateSource, deleteSource } from "@/lib/api";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function SourcesPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", base_url: "" });

  const sources = useQuery({ queryKey: ["sources"], queryFn: getSources });

  const add = useMutation({
    mutationFn: createSource,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["sources"] }); setOpen(false); setForm({ name: "", base_url: "" }); toast.success("Source added"); },
    onError: (e: Error) => toast.error(e.message),
  });

  const toggle = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => updateSource(id, { is_active }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["sources"] }); toast.success("Source updated"); },
  });

  const remove = useMutation({
    mutationFn: deleteSource,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["sources"] }); toast.success("Source deleted"); },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Sources</h1>
          <p className="text-sm text-zinc-400 mt-1">Manage news sources for scraping</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2 bg-blue-600 hover:bg-blue-500"><Plus className="h-4 w-4" /> Add Source</Button>
          </DialogTrigger>
          <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100">
            <DialogHeader><DialogTitle>Add New Source</DialogTitle></DialogHeader>
            <div className="space-y-4 mt-2">
              <div className="space-y-1.5">
                <Label className="text-zinc-400">Name</Label>
                <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. CoinDesk" className="bg-zinc-800 border-zinc-700 text-zinc-100" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400">Base URL</Label>
                <Input value={form.base_url} onChange={e => setForm(f => ({ ...f, base_url: e.target.value }))}
                  placeholder="https://coindesk.com" className="bg-zinc-800 border-zinc-700 text-zinc-100" />
              </div>
              <Button onClick={() => add.mutate(form)} disabled={add.isPending || !form.name || !form.base_url}
                className="w-full bg-blue-600 hover:bg-blue-500">
                {add.isPending ? "Adding..." : "Add Source"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded-lg border border-zinc-800 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-400">Name</TableHead>
              <TableHead className="text-zinc-400">Base URL</TableHead>
              <TableHead className="text-zinc-400 w-24">Status</TableHead>
              <TableHead className="text-zinc-400 w-20">Active</TableHead>
              <TableHead className="text-zinc-400 w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sources.isLoading
              ? Array(3).fill(0).map((_, i) => (
                <TableRow key={i} className="border-zinc-800">
                  {Array(5).fill(0).map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full bg-zinc-800" /></TableCell>)}
                </TableRow>
              ))
              : sources.data?.map(s => (
                <TableRow key={s._id} className="border-zinc-800 hover:bg-zinc-900">
                  <TableCell className="font-medium text-zinc-200">{s.name}</TableCell>
                  <TableCell className="text-zinc-400 text-sm">{s.base_url}</TableCell>
                  <TableCell>
                    <Badge className={s.is_active ? "bg-green-900/60 text-green-300" : "bg-zinc-800 text-zinc-500"}>
                      {s.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Switch checked={s.is_active} onCheckedChange={(v: boolean) => toggle.mutate({ id: s._id, is_active: v })} />
                  </TableCell>
                  <TableCell>
                    <button onClick={() => remove.mutate(s._id)} className="text-zinc-600 hover:text-red-400 transition-colors">
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
