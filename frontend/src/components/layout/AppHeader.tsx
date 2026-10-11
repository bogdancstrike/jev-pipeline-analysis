import { DesktopOutlined, MoonOutlined, SunOutlined } from "@ant-design/icons";
import { Segmented, Tooltip } from "antd";

import { useTheme, type Appearance } from "../../theme/ThemeProvider";
import { ServiceStatus } from "./ServiceStatus";

export function AppHeader({ onHome }: { onHome: () => void }) {
  const { appearance, setAppearance } = useTheme();
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <button type="button" className="brand" onClick={onHome} aria-label="Text triage home">
          <span className="brand-mark" aria-hidden><span /><span /><span /></span>
          <span className="brand-name">Text triage</span>
          <span className="brand-tag">on-prem</span>
        </button>
        <div className="header-right">
          <ServiceStatus />
          <Segmented<Appearance>
            size="small"
            value={appearance}
            onChange={setAppearance}
            aria-label="Appearance"
            options={[
              { value: "light", icon: <Tooltip title="Light"><SunOutlined /></Tooltip> },
              { value: "system", icon: <Tooltip title="Follow the system"><DesktopOutlined /></Tooltip> },
              { value: "dark", icon: <Tooltip title="Dark"><MoonOutlined /></Tooltip> },
            ]}
          />
        </div>
      </div>
    </header>
  );
}
