"use client";
import { useState } from "react";
import Copilot from "@/components/Copilot";
import type { PathData } from "@/lib/api";
export default function CopilotWorkspace(){const[data,setData]=useState<PathData|null>(null);return <Copilot data={data} onPath={setData}/>}
