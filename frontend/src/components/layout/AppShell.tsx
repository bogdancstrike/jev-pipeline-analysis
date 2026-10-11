import {
  DashboardOutlined, DesktopOutlined, MenuFoldOutlined, MenuUnfoldOutlined, MoonOutlined, PlusCircleOutlined,
  SettingOutlined, SunOutlined, UnorderedListOutlined,
} from "@ant-design/icons";
import { Button, Layout, Menu, Progress, Segmented, Tooltip } from "antd";
import type { ReactNode } from "react";

import { useJobs } from "../../hooks/queries";
import type { Page } from "../../hooks/useRoute";
import { useStoredState } from "../../hooks/useUrlState";
import { useTheme, type Appearance } from "../../theme/ThemeProvider";
import { ServiceStatus } from "./ServiceStatus";

const TITLES: Record<Page, string> = { new: "New analysis", runs: "Runs", dashboard: "Dashboard", admin: "Admin" };

/** Sidebar navigation + slim top bar; content takes the full width. */
export function AppShell({ page, title, onNavigate, onOpenJob, children }: {
  page: Page; title?: string; onNavigate: (p: Page) => void; onOpenJob: (id: string) => void; children: ReactNode;
}) {
  const { appearance, setAppearance } = useTheme();
  const [collapsed, setCollapsed] = useStoredState<boolean>("triage.sidebar.collapsed", false);
  const jobs = useJobs();
  const running = (jobs.data ?? []).filter((j) => j.status === "running" || j.status === "queued");

  return (
    <Layout className="shell" hasSider>
      <Layout.Sider collapsible collapsed={collapsed} trigger={null} width={224} collapsedWidth={64}
                    className="sider" breakpoint="lg" onBreakpoint={(broken) => broken && setCollapsed(true)}>
        <button type="button" className="brand" onClick={() => onNavigate("new")} aria-label="Text triage home">
          <span className="brand-mark" aria-hidden><span /><span /><span /></span>
          {!collapsed && <span className="brand-name">Text triage</span>}
        </button>
        <Menu mode="inline" selectedKeys={[page]} onClick={(e) => onNavigate(e.key as Page)} className="sider-menu"
              items={[
                { key: "new", icon: <PlusCircleOutlined />, label: "New analysis" },
                { key: "runs", icon: <UnorderedListOutlined />, label: "Runs" },
                { key: "dashboard", icon: <DashboardOutlined />, label: "Dashboard" },
                { key: "admin", icon: <SettingOutlined />, label: "Admin" },
              ]} />
        {running.length > 0 && (
          <div className="sider-running">
            {!collapsed && <div className="section-title">Running</div>}
            {running.slice(0, 3).map((j) => (
              <Tooltip key={j.id} title={`${j.filename}: ${j.done.toLocaleString()} / ${j.total.toLocaleString()} records`} placement="right">
                <button type="button" className="sider-job" onClick={() => onOpenJob(j.id)}>
                  {collapsed ? <Progress type="circle" size={28} percent={Math.floor(j.percent)} /> : (
                    <>
                      <span className="sider-job-name">{j.filename}</span>
                      <Progress percent={Math.floor(j.percent)} size="small" status="active" />
                    </>
                  )}
                </button>
              </Tooltip>
            ))}
          </div>
        )}
        <div className="sider-foot">
          <Button type="text" size="small" onClick={() => setCollapsed(!collapsed)}
                  icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                  aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} />
        </div>
      </Layout.Sider>
      <Layout>
        <header className="topbar">
          <nav className="crumbs" aria-label="Breadcrumb">
            <span className="crumb-app">Text triage</span>
            <span className="crumb-sep">/</span>
            <h1 className="topbar-title">{TITLES[page]}</h1>
            {title && <><span className="crumb-sep">/</span><span className="crumb-leaf">{title}</span></>}
          </nav>
          <div className="header-right">
            <ServiceStatus />
            <Segmented<Appearance> size="small" value={appearance} onChange={setAppearance} aria-label="Appearance"
              options={[
                { value: "light", icon: <Tooltip title="Light"><SunOutlined /></Tooltip> },
                { value: "system", icon: <Tooltip title="Follow the system"><DesktopOutlined /></Tooltip> },
                { value: "dark", icon: <Tooltip title="Dark"><MoonOutlined /></Tooltip> },
              ]} />
          </div>
        </header>
        <main id="main" className="app-main">{children}</main>
      </Layout>
    </Layout>
  );
}
