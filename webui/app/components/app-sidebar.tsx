"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { NAV_ITEMS } from "@/components/nav-items";

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-1.5">
          <span className="text-sm font-semibold group-data-[collapsible=icon]:hidden">
            leadgen
          </span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_ITEMS.map(({ cim, ut, ikon: Ikon }) => {
                const aktiv = ut === "/" ? pathname === "/" : pathname.startsWith(ut);
                return (
                  <SidebarMenuItem key={ut}>
                    <SidebarMenuButton
                      render={
                        <Link href={ut}>
                          <Ikon />
                          <span>{cim}</span>
                        </Link>
                      }
                      isActive={aktiv}
                      tooltip={cim}
                    />
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
