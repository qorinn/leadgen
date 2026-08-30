"use client";

import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronsUpDown, SlidersHorizontal } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";

interface AdatTablaProps<TData> {
  oszlopok: ColumnDef<TData, unknown>[];
  adat: TData[];
  /** 1-indexelt aktualis oldal. */
  oldal: number;
  oldalMeret: number;
  osszesen: number;
  onOldalValtas: (oldal: number) => void;
  /** Szerver-oldali rendezes -- ha nincs megadva, az oszlop nem rendezheto. */
  rendezes?: SortingState;
  onRendezesValtas?: (rendezes: SortingState) => void;
  betoltes?: boolean;
  hiba?: string | null;
  ujra?: () => void;
  /** Uzenet, ha `osszesen === 0` es nincs hiba -- pl. <UresAllapot />. */
  ures?: ReactNode;
  /** Szures-vezerlok az oszlopvalaszto elott. */
  toolbar?: ReactNode;
}

/** Szerver-oldali szures, rendezes, lapozas + oszlopvalaszto (WEBUI-TERV.md
 * F2 -- ez a minta minden kesobbi listanezethez, pl. F4 cegek). A szures
 * maga az adatlekerest inditja a hivo oldalon: ez a komponens csak
 * megjelenit es esemenyt ad vissza, adatot nem tarol. */
export function AdatTabla<TData>({
  oszlopok,
  adat,
  oldal,
  oldalMeret,
  osszesen,
  onOldalValtas,
  rendezes,
  onRendezesValtas,
  betoltes,
  hiba,
  ujra,
  ures,
  toolbar,
}: AdatTablaProps<TData>) {
  const [oszlopLathatosag, setOszlopLathatosag] = useState<VisibilityState>({});

  const table = useReactTable({
    data: adat,
    columns: oszlopok,
    state: { sorting: rendezes ?? [], columnVisibility: oszlopLathatosag },
    manualPagination: true,
    manualSorting: true,
    onSortingChange: (updater) => {
      if (!onRendezesValtas) return;
      const uj = typeof updater === "function" ? updater(rendezes ?? []) : updater;
      onRendezesValtas(uj);
    },
    onColumnVisibilityChange: setOszlopLathatosag,
    getCoreRowModel: getCoreRowModel(),
    pageCount: Math.max(1, Math.ceil(osszesen / oldalMeret)),
  });

  const elsoSor = osszesen === 0 ? 0 : (oldal - 1) * oldalMeret + 1;
  const utolsoSor = Math.min(oldal * oldalMeret, osszesen);
  const utolsoOldal = Math.max(1, Math.ceil(osszesen / oldalMeret));

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex-1">{toolbar}</div>
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}>
            <SlidersHorizontal className="size-4" />
            Oszlopok
            <ChevronDown className="size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {table
              .getAllColumns()
              .filter((oszlop) => oszlop.getCanHide())
              .map((oszlop) => (
                <DropdownMenuCheckboxItem
                  key={oszlop.id}
                  checked={oszlop.getIsVisible()}
                  onCheckedChange={(ertek) => oszlop.toggleVisibility(!!ertek)}
                  onSelect={(e) => e.preventDefault()}
                >
                  {oszlop.id}
                </DropdownMenuCheckboxItem>
              ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {hiba ? (
        <HibaAllapot uzenet={hiba} ujra={ujra} />
      ) : betoltes ? (
        <Betoltes sorok={oldalMeret > 8 ? 8 : oldalMeret} />
      ) : osszesen === 0 && ures ? (
        ures
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => {
                    const rendezheto = onRendezesValtas && header.column.getCanSort();
                    return (
                      <TableHead
                        key={header.id}
                        className={rendezheto ? "cursor-pointer select-none" : undefined}
                        onClick={
                          rendezheto ? header.column.getToggleSortingHandler() : undefined
                        }
                      >
                        {header.isPlaceholder ? null : (
                          <span className="inline-flex items-center gap-1">
                            {flexRender(header.column.columnDef.header, header.getContext())}
                            {rendezheto && (
                              <ChevronsUpDown className="size-3.5 text-muted-foreground" />
                            )}
                          </span>
                        )}
                      </TableHead>
                    );
                  })}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {!hiba && osszesen > 0 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {elsoSor}–{utolsoSor} / {osszesen}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={oldal <= 1}
              onClick={() => onOldalValtas(oldal - 1)}
            >
              <ChevronLeft className="size-4" />
              Előző
            </Button>
            <span>
              {oldal} / {utolsoOldal}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={oldal >= utolsoOldal}
              onClick={() => onOldalValtas(oldal + 1)}
            >
              Következő
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
