"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const OPCIOK = [
  { ertek: "light", cimke: "Világos", ikon: Sun },
  { ertek: "dark", cimke: "Sötét", ikon: Moon },
  { ertek: "system", cimke: "Rendszer", ikon: Monitor },
] as const;

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  // A next-themes csak kliensen tudja a tenyleges temat -- SSR alatt
  // hydration-eltmerest okozna, ha korabban rendernenk az ikont.
  const [csatlakozva, setCsatlakozva] = useState(false);
  useEffect(() => setCsatlakozva(true), []);

  const Aktiv = OPCIOK.find((o) => o.ertek === theme)?.ikon ?? Monitor;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant="ghost" size="icon" aria-label="Téma váltása" />}>
        {csatlakozva ? <Aktiv className="size-4" /> : <Monitor className="size-4" />}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {OPCIOK.map(({ ertek, cimke, ikon: Ikon }) => (
          <DropdownMenuItem key={ertek} onClick={() => setTheme(ertek)}>
            <Ikon className="size-4" />
            {cimke}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
