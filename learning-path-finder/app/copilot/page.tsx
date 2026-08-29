import Header from "@/components/Header";
import Sidebar from "@/components/Sidebar";
import CopilotWorkspace from "@/components/CopilotWorkspace";
export default function CopilotPage(){return <div className="app-shell"><Sidebar/><div className="app-content"><Header/><main className="dashboard subpage"><p className="eyebrow"><span className="pulse-dot"/> Your learning companion</p><h1>Talk it through.<br/><em>Build what fits.</em></h1><p className="subpage-intro">ALMA uses your answers to understand your current skills, time, and target—then asks the engine to build the path.</p><CopilotWorkspace/></main></div></div>}
