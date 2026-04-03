import { Info } from "@phosphor-icons/react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export default function InfoTooltip({ text, side = "top" }) {
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            data-testid="info-tooltip-trigger"
            className="inline-flex items-center justify-center w-4 h-4 rounded-full text-[#737373] hover:text-[#007AFF] transition-colors cursor-help"
          >
            <Info weight="fill" className="w-3.5 h-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent
          side={side}
          className="max-w-[260px] bg-[#1F1F1F] border border-[#333] text-[#D4D4D4] text-[11px] leading-relaxed px-3 py-2 rounded-md shadow-xl"
        >
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
