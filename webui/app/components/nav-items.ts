import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  BarChart3,
  LayoutDashboard,
  MessageSquare,
  Play,
  Send,
  Settings,
  Users,
} from "lucide-react";

export interface NavItem {
  cim: string;
  ut: string;
  ikon: LucideIcon;
}

// A menu-sorrend es a magyar feliratok itt vannak drotozva -- ez
// megjelenitesi dontes, nem uzleti szabaly, tehat nem kell a /api/meta-bol
// jonnie (WEBUI-TERV.md Invariansok #1).
export const NAV_ITEMS: NavItem[] = [
  { cim: "Irányítópult", ut: "/", ikon: LayoutDashboard },
  { cim: "Cégek", ut: "/cegek", ikon: Users },
  { cim: "Válaszok", ut: "/valaszok", ikon: MessageSquare },
  { cim: "Riasztások", ut: "/riasztasok", ikon: AlertTriangle },
  { cim: "Futtatás", ut: "/futtatas", ikon: Play },
  { cim: "Küldés", ut: "/kuldes", ikon: Send },
  { cim: "Riportok", ut: "/riportok", ikon: BarChart3 },
  { cim: "Beállítások", ut: "/beallitasok", ikon: Settings },
];
