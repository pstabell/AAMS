"use client";

import { useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";

export default function DynamicTitle() {
  const { currentFloor } = useAuth();

  useEffect(() => {
    document.title =
      currentFloor === 2
        ? "Agency Commission Tracker"
        : "Agent Commission Tracker";
  }, [currentFloor]);

  return null;
}
