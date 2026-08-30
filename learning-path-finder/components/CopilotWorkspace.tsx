"use client";
import Copilot from "@/components/Copilot";
import { usePathData } from "@/lib/store";

export default function CopilotWorkspace() {
  const [data, setData] = usePathData();
  return <Copilot data={data} onPath={setData} />;
}
