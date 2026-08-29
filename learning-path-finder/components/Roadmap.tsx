"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { CheckCircle2, Circle } from "lucide-react";

export default function Roadmap({ view, data }: { view: 'condensed' | 'breakdown', data: any }) {
  return (
    <div className="flex flex-col items-center gap-12 py-20 overflow-y-auto h-full scrollbar-hide">
      {data.map((node: any, index: number) => (
        <div key={node.id} className="relative flex flex-col items-center">
          {/* Connection Line */}
          {index !== data.length - 1 && (
            <div className="absolute top-16 w-1 h-20 bg-aqua/20" />
          )}
          
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            className={cn(
              "relative z-10 w-20 h-20 rounded-full border-4 flex items-center justify-center transition-all",
              node.completed ? "border-aqua bg-aqua text-iron" : "border-aqua/30 bg-iron text-aqua"
            )}
          >
            {/* Progress Ring */}
            <svg className="absolute -inset-2 w-24 h-24 rotate-[-90deg]">
              <circle
                cx="48"
                cy="48"
                r="44"
                fill="transparent"
                stroke="currentColor"
                strokeWidth="4"
                strokeDasharray={276}
                strokeDashoffset={276 - (276 * node.progress) / 100}
                className={node.completed ? "text-aqua" : "text-heat"}
              />
            </svg>
            {node.completed ? <CheckCircle2 size={32} /> : <Circle size={32} />}
          </motion.button>
          
          <span className="mt-6 font-bold text-cream text-sm uppercase tracking-widest bg-iron px-4 py-1 border border-aqua/20">
            {node.label}
          </span>
        </div>
      ))}
    </div>
  );
}
