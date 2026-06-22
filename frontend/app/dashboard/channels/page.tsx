"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getChannels, createChannel, updateChannel, deleteChannel } from "@/lib/api";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, Trash2, Clock } from "lucide-react";
import { toast } from "sonner";

export default function ChannelsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", telegram_id: "", post_interval_minutes: 60 });

  const channels = useQuery({ queryKey: ["channels"], queryFn: getChannels });

  const add = useMutation({
    mutationFn: createChannel,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["channels"] }); setOpen(false); setForm({ name: "", telegram_id: "", post_interval_minutes: 60 }); toast.success("Channel added"); },
    onError: (e: Error) => toast.error(e.message),
  });

  const toggle = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => updateChannel(id, { is_active }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["channels"] }); toast.success("Channel updated"); },
  });

  const remove = useMutation({
    mutationFn: deleteChannel,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["channels"] }); toast.success("Channel deleted"); },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Channels</h1>
          <p className="text-sm text-zinc-400 mt-1">Telegram channels to post articles to</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2 bg-blue-600 hover:bg-blue-500"><Plus className="h-4 w-4" /> Add Channel</Button>
          </DialogTrigger>
          <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100">
            <DialogHeader><DialogTitle>Add Telegram Channel</DialogTitle></DialogHeader>
            <div className="space-y-4 mt-2">
              <div className="space-y-1.5">
                <Label className="text-zinc-400">Channel Name</Label>
                <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Crypto News" className="bg-zinc-800 border-zinc-700 text-zinc-100" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400">Telegram Channel ID</Label>
                <Input value={form.telegram_id} onChange={e => setForm(f => ({ ...f, telegram_id: e.target.value }))}
                  placeholder="@yourchannel or -100xxxxxxxxxx" className="bg-zinc-800 border-zinc-700 text-zinc-100" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400">Post Interval (minutes)</Label>
                <Input type="number" value={form.post_interval_minutes}
                  onChange={e => setForm(f => ({ ...f, post_interval_minutes: parseInt(e.target.value) || 60 }))}
                  className="bg-zinc-800 border-zinc-700 text-zinc-100" />
              </div>
              <Button onClick={() => add.mutate(form)} disabled={add.isPending || !form.name || !form.telegram_id}
                className="w-full bg-blue-600 hover:bg-blue-500">
                {add.isPending ? "Adding..." : "Add Channel"}
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
              <TableHead className="text-zinc-400">Telegram ID</TableHead>
              <TableHead className="text-zinc-400 w-32">Post Interval</TableHead>
              <TableHead className="text-zinc-400 w-24">Status</TableHead>
              <TableHead className="text-zinc-400 w-20">Active</TableHead>
              <TableHead className="text-zinc-400 w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {channels.isLoading
              ? Array(2).fill(0).map((_, i) => (
                <TableRow key={i} className="border-zinc-800">
                  {Array(6).fill(0).map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full bg-zinc-800" /></TableCell>)}
                </TableRow>
              ))
              : channels.data?.map(c => (
                <TableRow key={c._id} className="border-zinc-800 hover:bg-zinc-900">
                  <TableCell className="font-medium text-zinc-200">{c.name}</TableCell>
                  <TableCell className="font-mono text-zinc-400 text-sm">{c.telegram_id}</TableCell>
                  <TableCell>
                    <span className="flex items-center gap-1.5 text-zinc-400 text-sm">
                      <Clock className="h-3.5 w-3.5" /> {c.post_interval_minutes}m
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge className={c.is_active ? "bg-green-900/60 text-green-300" : "bg-zinc-800 text-zinc-500"}>
                      {c.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Switch checked={c.is_active} onCheckedChange={(v: boolean) => toggle.mutate({ id: c._id, is_active: v })} />
                  </TableCell>
                  <TableCell>
                    <button onClick={() => remove.mutate(c._id)} className="text-zinc-600 hover:text-red-400 transition-colors">
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
