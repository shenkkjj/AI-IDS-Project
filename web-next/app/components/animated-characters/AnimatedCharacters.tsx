"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import gsap from "gsap";
import EyeBall from "./EyeBall";
import Pupil from "./Pupil";

interface AnimatedCharactersProps {
  isTyping?: boolean;
  showPassword?: boolean;
  passwordLength?: number;
  activeCharacter?: string | null;
}

type CharacterMood = "normal" | "happy" | "surprised" | "sleepy" | "excited" | "hacking" | "locked" | "unlocked";

const HACKER_COLORS = {
  purple: {
    bodyGradient: "linear-gradient(180deg, #2d1b4e 0%, #1a0a2e 100%)",
    glow: "#9d4edd",
    glowShadow: "0 0 20px rgba(157, 78, 221, 0.4), 0 0 40px rgba(157, 78, 221, 0.2), inset 0 0 20px rgba(157, 78, 221, 0.1)",
    eyeColor: "#00ff41",
    pupilColor: "#9d4edd",
    border: "1px solid rgba(157, 78, 221, 0.3)",
  },
  black: {
    bodyGradient: "linear-gradient(180deg, #161b22 0%, #0d1117 100%)",
    glow: "#00ff41",
    glowShadow: "0 0 20px rgba(0, 255, 65, 0.4), 0 0 40px rgba(0, 255, 65, 0.2), inset 0 0 20px rgba(0, 255, 65, 0.1)",
    eyeColor: "#00ff41",
    pupilColor: "#ffffff",
    border: "1px solid rgba(0, 255, 65, 0.3)",
  },
  orange: {
    bodyGradient: "linear-gradient(180deg, #4a2512 0%, #2d1810 100%)",
    glow: "#ff6b35",
    glowShadow: "0 0 20px rgba(255, 107, 53, 0.4), 0 0 40px rgba(255, 107, 53, 0.2), inset 0 0 20px rgba(255, 107, 53, 0.1)",
    eyeColor: "#ff6b35",
    pupilColor: "#ffdd00",
    border: "1px solid rgba(255, 107, 53, 0.3)",
  },
  yellow: {
    bodyGradient: "linear-gradient(180deg, #4a4512 0%, #2d2a0a 100%)",
    glow: "#ffdd00",
    glowShadow: "0 0 20px rgba(255, 221, 0, 0.4), 0 0 40px rgba(255, 221, 0, 0.2), inset 0 0 20px rgba(255, 221, 0, 0.1)",
    eyeColor: "#ffdd00",
    pupilColor: "#ff6b35",
    border: "1px solid rgba(255, 221, 0, 0.3)",
  },
};

const generateBinary = (length: number) => {
  return Array.from({ length }, () => Math.random() > 0.5 ? "1" : "0").join("");
};

const generateHex = (length: number) => {
  return Array.from({ length }, () => Math.floor(Math.random() * 16).toString(16).toUpperCase()).join("");
};

export default function AnimatedCharacters({
  isTyping = false,
  showPassword = false,
  passwordLength = 0,
  activeCharacter = null,
}: AnimatedCharactersProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mouseRef = useRef({ x: 0, y: 0 });
  const rafIdRef = useRef<number>(0);

  const purpleRef = useRef<HTMLDivElement>(null);
  const blackRef = useRef<HTMLDivElement>(null);
  const yellowRef = useRef<HTMLDivElement>(null);
  const orangeRef = useRef<HTMLDivElement>(null);

  const purpleFaceRef = useRef<HTMLDivElement>(null);
  const blackFaceRef = useRef<HTMLDivElement>(null);
  const yellowFaceRef = useRef<HTMLDivElement>(null);
  const orangeFaceRef = useRef<HTMLDivElement>(null);
  const yellowMouthRef = useRef<HTMLDivElement>(null);

  const quickToRef = useRef<Record<string, gsap.QuickToFunc> | null>(null);
  const stateRef = useRef({
    isTyping: false,
    isHidingPassword: false,
    isShowingPassword: false,
    isLooking: false,
  });

  const [moods, setMoods] = useState<Record<string, CharacterMood>>({
    purple: "normal",
    black: "normal",
    orange: "normal",
    yellow: "normal",
  });

  const [binaryCodes, setBinaryCodes] = useState({
    purple: "1000100101101001",
    black: "110101101011",
    orange: "10100101110011",
    yellow: "1100101101",
  });

  const [hexCodes, setHexCodes] = useState({
    purple: "A3F7B2D1",
    black: "E8C4A2",
    orange: "FF6B35DD00",
    yellow: "FFD700AB",
  });

  const isHidingPassword = passwordLength > 0 && !showPassword;
  const isShowingPassword = passwordLength > 0 && showPassword;

  useEffect(() => {
    stateRef.current.isTyping = isTyping;
    stateRef.current.isHidingPassword = isHidingPassword;
    stateRef.current.isShowingPassword = isShowingPassword;
  }, [isTyping, isHidingPassword, isShowingPassword]);

  useEffect(() => {
    const interval = setInterval(() => {
      setBinaryCodes({
        purple: generateBinary(16),
        black: generateBinary(12),
        orange: generateBinary(14),
        yellow: generateBinary(10),
      });
      setHexCodes({
        purple: generateHex(8),
        black: generateHex(6),
        orange: generateHex(10),
        yellow: generateHex(8),
      });
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  // Active character effect
  useEffect(() => {
    if (!activeCharacter) return;
    
    const charRef = activeCharacter === "purple" ? purpleRef.current :
                    activeCharacter === "black" ? blackRef.current :
                    activeCharacter === "orange" ? orangeRef.current :
                    yellowRef.current;

    if (charRef) {
      gsap.to(charRef, {
        boxShadow: HACKER_COLORS[activeCharacter as keyof typeof HACKER_COLORS].glowShadow + ", 0 0 60px " + HACKER_COLORS[activeCharacter as keyof typeof HACKER_COLORS].glow,
        duration: 0.3,
        yoyo: true,
        repeat: 3,
      });
    }
  }, [activeCharacter]);

  const calcPos = useCallback((el: HTMLElement, cached?: DOMRect) => {
    const rect = cached || el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 3;
    const dx = mouseRef.current.x - cx;
    const dy = mouseRef.current.y - cy;
    return {
      faceX: Math.max(-15, Math.min(15, dx / 20)),
      faceY: Math.max(-10, Math.min(10, dy / 30)),
      bodySkew: Math.max(-6, Math.min(6, -dx / 120)),
    };
  }, []);

  const calcEyePos = useCallback((el: HTMLElement, maxDist: number, cached?: DOMRect) => {
    const r = cached || el.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    const dx = mouseRef.current.x - cx;
    const dy = mouseRef.current.y - cy;
    const dist = Math.min(Math.sqrt(dx ** 2 + dy ** 2), maxDist);
    const angle = Math.atan2(dy, dx);
    return { x: Math.cos(angle) * dist, y: Math.sin(angle) * dist };
  }, []);

  // Throttled mouse position update to reduce rAF calculations
  const mousePosRef = useRef({ x: 0, y: 0 });
  const lastMouseUpdateRef = useRef(0);

  const handleCharacterClick = useCallback((character: string) => {
    const moodsList: CharacterMood[] = ["normal", "hacking", "surprised", "locked", "unlocked"];
    const currentMood = moods[character];
    const nextMood = moodsList[(moodsList.indexOf(currentMood) + 1) % moodsList.length];
    
    setMoods(prev => ({ ...prev, [character]: nextMood }));

    const charRef = character === "purple" ? purpleRef.current :
                    character === "black" ? blackRef.current :
                    character === "orange" ? orangeRef.current :
                    yellowRef.current;

    if (charRef) {
      // Unique reaction per character - more dramatic
      if (character === "purple") {
        // Matrix glitch + color flash
        const tl = gsap.timeline();
        tl.to(charRef, { x: "+=4", filter: "hue-rotate(90deg)", duration: 0.06, repeat: 7, yoyo: true })
          .to(charRef, { filter: "hue-rotate(0deg)", duration: 0.2 });
        // Spawn floating binary particles
        for (let i = 0; i < 5; i++) {
          const particle = document.createElement("div");
          particle.textContent = Math.random() > 0.5 ? "1" : "0";
          particle.style.cssText = `position:absolute;font-family:monospace;font-size:10px;color:#00ff41;pointer-events:none;z-index:50;left:${50 + Math.random() * 80}px;top:${20 + Math.random() * 60}px;`;
          charRef.appendChild(particle);
          gsap.to(particle, { y: -40, opacity: 0, duration: 1, delay: i * 0.1, onComplete: () => particle.remove() });
        }
      } else if (character === "black") {
        // Terminal typing shake + scan line
        const tl = gsap.timeline();
        tl.to(charRef, { skewX: 8, scaleX: 1.05, duration: 0.08, repeat: 5, yoyo: true })
          .to(charRef, { skewX: 0, scaleX: 1, duration: 0.3 });
      } else if (character === "orange") {
        // Alert pulse + glow burst
        const tl = gsap.timeline();
        tl.to(charRef, { scale: 1.15, boxShadow: `0 0 40px ${HACKER_COLORS.orange.glow}, 0 0 80px ${HACKER_COLORS.orange.glow}`, duration: 0.15, repeat: 5, yoyo: true })
          .to(charRef, { scale: 1, boxShadow: HACKER_COLORS.orange.glowShadow, duration: 0.4 });
      } else {
        // Data stream bounce + spin
        const tl = gsap.timeline();
        tl.to(charRef, { y: -25, rotation: 5, duration: 0.25, ease: "back.out(3)", repeat: 3, yoyo: true })
          .to(charRef, { rotation: 0, duration: 0.3 });
      }
    }

    setTimeout(() => {
      setMoods(prev => ({ ...prev, [character]: "normal" }));
    }, 3000);
  }, [moods]);

  const handleCharacterHover = useCallback((character: string, isEntering: boolean) => {
    const charRef = character === "purple" ? purpleRef.current :
                    character === "black" ? blackRef.current :
                    character === "orange" ? orangeRef.current :
                    yellowRef.current;

    if (charRef) {
      if (isEntering) {
        gsap.to(charRef, {
          scale: 1.05,
          duration: 0.3,
          ease: "back.out(1.7)",
        });
      } else {
        gsap.to(charRef, {
          scale: 1,
          duration: 0.3,
          ease: "power2.out",
        });
      }
    }
  }, []);

  useEffect(() => {
    if (
      !purpleRef.current ||
      !blackRef.current ||
      !orangeRef.current ||
      !yellowRef.current ||
      !purpleFaceRef.current ||
      !blackFaceRef.current ||
      !orangeFaceRef.current ||
      !yellowFaceRef.current ||
      !yellowMouthRef.current
    )
      return;

    const qt = {
      purpleSkew: gsap.quickTo(purpleRef.current, "skewX", { duration: 0.3, ease: "power2.out" }),
      blackSkew: gsap.quickTo(blackRef.current, "skewX", { duration: 0.3, ease: "power2.out" }),
      orangeSkew: gsap.quickTo(orangeRef.current, "skewX", { duration: 0.3, ease: "power2.out" }),
      yellowSkew: gsap.quickTo(yellowRef.current, "skewX", { duration: 0.3, ease: "power2.out" }),
      purpleX: gsap.quickTo(purpleRef.current, "x", { duration: 0.3, ease: "power2.out" }),
      blackX: gsap.quickTo(blackRef.current, "x", { duration: 0.3, ease: "power2.out" }),
      purpleHeight: gsap.quickTo(purpleRef.current, "height", { duration: 0.3, ease: "power2.out" }),
      purpleFaceLeft: gsap.quickTo(purpleFaceRef.current, "left", { duration: 0.3, ease: "power2.out" }),
      purpleFaceTop: gsap.quickTo(purpleFaceRef.current, "top", { duration: 0.3, ease: "power2.out" }),
      blackFaceLeft: gsap.quickTo(blackFaceRef.current, "left", { duration: 0.3, ease: "power2.out" }),
      blackFaceTop: gsap.quickTo(blackFaceRef.current, "top", { duration: 0.3, ease: "power2.out" }),
      orangeFaceX: gsap.quickTo(orangeFaceRef.current, "x", { duration: 0.2, ease: "power2.out" }),
      orangeFaceY: gsap.quickTo(orangeFaceRef.current, "y", { duration: 0.2, ease: "power2.out" }),
      yellowFaceX: gsap.quickTo(yellowFaceRef.current, "x", { duration: 0.2, ease: "power2.out" }),
      yellowFaceY: gsap.quickTo(yellowFaceRef.current, "y", { duration: 0.2, ease: "power2.out" }),
      mouthX: gsap.quickTo(yellowMouthRef.current, "x", { duration: 0.2, ease: "power2.out" }),
      mouthY: gsap.quickTo(yellowMouthRef.current, "y", { duration: 0.2, ease: "power2.out" }),
      mouthWidth: gsap.quickTo(yellowMouthRef.current, "width", { duration: 0.2, ease: "power2.out" }),
      mouthHeight: gsap.quickTo(yellowMouthRef.current, "height", { duration: 0.2, ease: "power2.out" }),
    };
    quickToRef.current = qt;

    gsap.set(".pupil", { x: 0, y: 0 });
    gsap.set(".eyeball-pupil", { x: 0, y: 0 });

    const posCache = new Map<HTMLElement, DOMRect>();
    let posCacheDirty = true;
    const updatePosCache = () => {
      if (!posCacheDirty) return;
      posCache.clear();
      [purpleRef.current, blackRef.current, orangeRef.current, yellowRef.current].forEach((el) => {
        if (el) posCache.set(el, el.getBoundingClientRect());
      });
      containerRef.current?.querySelectorAll(".pupil").forEach((p) => {
        const el = p as HTMLElement;
        posCache.set(el, el.getBoundingClientRect());
      });
      containerRef.current?.querySelectorAll(".eyeball").forEach((eb) => {
        const el = eb as HTMLElement;
        posCache.set(el, el.getBoundingClientRect());
      });
      posCacheDirty = false;
    };
    updatePosCache();

    let cachedPupils: HTMLElement[] = Array.from(containerRef.current?.querySelectorAll(".pupil") ?? []) as HTMLElement[];
    let cachedEyeballs: HTMLElement[] = Array.from(containerRef.current?.querySelectorAll(".eyeball") ?? []) as HTMLElement[];

    const onResize = () => {
      posCacheDirty = true;
      cachedPupils = Array.from(containerRef.current?.querySelectorAll(".pupil") ?? []) as HTMLElement[];
      cachedEyeballs = Array.from(containerRef.current?.querySelectorAll(".eyeball") ?? []) as HTMLElement[];
    };
    window.addEventListener("resize", onResize, { passive: true });

    const tick = () => {
      const container = containerRef.current;
      if (!container) return;

      // Update position cache if dirty (e.g., after resize)
      updatePosCache();

      const { isTyping: typing, isHidingPassword: hiding, isShowingPassword: showing, isLooking: looking } = stateRef.current;

      if (purpleRef.current && !showing) {
        const pp = calcPos(purpleRef.current, posCache.get(purpleRef.current));
        if (typing || hiding) {
          qt.purpleSkew(pp.bodySkew - 12);
          qt.purpleX(40);
          qt.purpleHeight(440);
        } else {
          qt.purpleSkew(pp.bodySkew);
          qt.purpleX(0);
          qt.purpleHeight(400);
        }
      }

      if (blackRef.current && !showing) {
        const bp = calcPos(blackRef.current, posCache.get(blackRef.current));
        if (looking) {
          qt.blackSkew(bp.bodySkew * 1.5 + 10);
          qt.blackX(20);
        } else if (typing || hiding) {
          qt.blackSkew(bp.bodySkew * 1.5);
          qt.blackX(0);
        } else {
          qt.blackSkew(bp.bodySkew);
          qt.blackX(0);
        }
      }

      if (orangeRef.current && !showing) {
        const op = calcPos(orangeRef.current, posCache.get(orangeRef.current));
        qt.orangeSkew(op.bodySkew);
      }

      if (yellowRef.current && !showing) {
        const yp = calcPos(yellowRef.current, posCache.get(yellowRef.current));
        qt.yellowSkew(yp.bodySkew);
      }

      if (purpleRef.current && !showing && !looking) {
        const pp = calcPos(purpleRef.current, posCache.get(purpleRef.current));
        const purpleFaceX = pp.faceX >= 0 ? Math.min(25, pp.faceX * 1.5) : pp.faceX;
        qt.purpleFaceLeft(45 + purpleFaceX);
        qt.purpleFaceTop(40 + pp.faceY);
      }

      if (blackRef.current && !showing && !looking) {
        const bp = calcPos(blackRef.current, posCache.get(blackRef.current));
        qt.blackFaceLeft(26 + bp.faceX);
        qt.blackFaceTop(32 + bp.faceY);
      }

      if (orangeRef.current && !showing) {
        const op = calcPos(orangeRef.current, posCache.get(orangeRef.current));
        qt.orangeFaceX(op.faceX);
        qt.orangeFaceY(op.faceY);
      }

      if (yellowRef.current && !showing) {
        const yp = calcPos(yellowRef.current, posCache.get(yellowRef.current));
        qt.yellowFaceX(yp.faceX);
        qt.yellowFaceY(yp.faceY);
        qt.mouthX(yp.faceX);
        qt.mouthY(yp.faceY);
      }

      if (!showing) {
        cachedPupils.forEach((el) => {
          const maxDist = Number(el.dataset.maxDistance) || 5;
          const ePos = calcEyePos(el, maxDist, posCache.get(el));
          gsap.set(el, { x: ePos.x, y: ePos.y });
        });

        if (!looking) {
          cachedEyeballs.forEach((el) => {
            const maxDist = Number(el.dataset.maxDistance) || 10;
            const pupil = el.querySelector(".eyeball-pupil") as HTMLElement;
            if (!pupil) return;
            const ePos = calcEyePos(el, maxDist, posCache.get(el));
            gsap.set(pupil, { x: ePos.x, y: ePos.y });
          });
        }
      }

      rafIdRef.current = requestAnimationFrame(tick);
    };

    const onMove = (e: MouseEvent) => {
      const now = performance.now();
      // Throttle mouse updates to every 16ms (~60fps) to reduce calculations
      if (now - lastMouseUpdateRef.current < 16) return;
      lastMouseUpdateRef.current = now;
      mouseRef.current.x = e.clientX;
      mouseRef.current.y = e.clientY;
    };

    window.addEventListener("mousemove", onMove, { passive: true });
    rafIdRef.current = requestAnimationFrame(tick);

    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("resize", onResize);
      cancelAnimationFrame(rafIdRef.current);
    };
  }, [calcPos, calcEyePos]);

  useEffect(() => {
    if (!quickToRef.current) return;
    const qt = quickToRef.current;

    if (isTyping && !showPassword) {
      stateRef.current.isLooking = true;
      qt.purpleFaceLeft(55);
      qt.purpleFaceTop(65);
      qt.blackFaceLeft(32);
      qt.blackFaceTop(12);

      purpleRef.current?.querySelectorAll(".eyeball-pupil").forEach((p) => {
        gsap.to(p, { x: 3, y: 4, duration: 0.3, ease: "power2.out", overwrite: "auto" });
      });
      blackRef.current?.querySelectorAll(".eyeball-pupil").forEach((p) => {
        gsap.to(p, { x: 0, y: -4, duration: 0.3, ease: "power2.out", overwrite: "auto" });
      });

      const timer = setTimeout(() => {
        stateRef.current.isLooking = false;
        purpleRef.current?.querySelectorAll(".eyeball-pupil").forEach((p) => {
          gsap.killTweensOf(p);
        });
      }, 800);

      return () => clearTimeout(timer);
    } else {
      stateRef.current.isLooking = false;
    }
  }, [isTyping, showPassword]);

  useEffect(() => {
    if (!quickToRef.current) return;
    const qt = quickToRef.current;

    if (showPassword && passwordLength > 0) {
      // All characters look away dramatically when password is shown
      qt.purpleSkew(-5);
      qt.blackSkew(-8);
      qt.orangeSkew(-5);
      qt.yellowSkew(-5);
      qt.purpleX(-15);
      qt.blackX(-10);
      qt.purpleHeight(380);

      // Faces turn away to the left
      qt.purpleFaceLeft(10);
      qt.purpleFaceTop(30);
      qt.blackFaceLeft(5);
      qt.blackFaceTop(25);
      qt.orangeFaceX(30 - 82);
      qt.orangeFaceY(75 - 90);
      qt.yellowFaceX(5 - 52);
      qt.yellowFaceY(25 - 40);
      qt.mouthX(-5 - 40);
      qt.mouthY(-2);

      // Pupils look far away to upper left
      purpleRef.current?.querySelectorAll(".eyeball-pupil").forEach((p) => {
        gsap.to(p, { x: -6, y: -6, duration: 0.4, ease: "back.out(2)", overwrite: "auto" });
      });
      blackRef.current?.querySelectorAll(".eyeball-pupil").forEach((p) => {
        gsap.to(p, { x: -6, y: -6, duration: 0.4, ease: "back.out(2)", overwrite: "auto" });
      });
      orangeRef.current?.querySelectorAll(".pupil").forEach((p) => {
        gsap.to(p, { x: -7, y: -6, duration: 0.4, ease: "back.out(2)", overwrite: "auto" });
      });
      yellowRef.current?.querySelectorAll(".pupil").forEach((p) => {
        gsap.to(p, { x: -7, y: -6, duration: 0.4, ease: "back.out(2)", overwrite: "auto" });
      });

      // Add "shy" blush effect via opacity
      [purpleRef, blackRef, orangeRef, yellowRef].forEach((ref) => {
        if (ref.current) {
          gsap.to(ref.current, { opacity: 0.7, duration: 0.3 });
        }
      });
    } else {
      // Restore opacity when not showing password
      [purpleRef, blackRef, orangeRef, yellowRef].forEach((ref) => {
        if (ref.current) {
          gsap.to(ref.current, { opacity: 1, duration: 0.3 });
        }
      });
      if (isHidingPassword) {
        qt.purpleFaceLeft(55);
        qt.purpleFaceTop(65);
      }
    }
  }, [showPassword, passwordLength, isHidingPassword]);

  useEffect(() => {
    if (!quickToRef.current) return;
    const qt = quickToRef.current;

    if (moods.purple === "hacking" && purpleRef.current) {
      gsap.to(purpleRef.current, { x: "+=2", duration: 0.05, repeat: 10, yoyo: true });
    }
    if (moods.black === "hacking" && blackRef.current) {
      gsap.to(blackRef.current, { skewX: 3, duration: 0.1, repeat: 5, yoyo: true });
    }
    if (moods.orange === "hacking" && orangeRef.current) {
      gsap.to(orangeRef.current, { scale: 1.05, duration: 0.2, repeat: 5, yoyo: true });
    }
    if (moods.yellow === "hacking" && yellowRef.current) {
      gsap.to(yellowRef.current, { y: -10, duration: 0.3, ease: "back.out(2)", repeat: 3, yoyo: true });
    }

    if (moods.purple === "surprised") {
      purpleRef.current?.querySelectorAll(".eyeball").forEach((el) => {
        gsap.to(el, { scale: 1.3, duration: 0.3, ease: "back.out(2)" });
      });
    } else {
      purpleRef.current?.querySelectorAll(".eyeball").forEach((el) => {
        gsap.to(el, { scale: 1, duration: 0.3 });
      });
    }

    if (moods.black === "surprised") {
      blackRef.current?.querySelectorAll(".eyeball").forEach((el) => {
        gsap.to(el, { scale: 1.3, duration: 0.3, ease: "back.out(2)" });
      });
    } else {
      blackRef.current?.querySelectorAll(".eyeball").forEach((el) => {
        gsap.to(el, { scale: 1, duration: 0.3 });
      });
    }

    if (moods.purple === "locked") {
      purpleRef.current?.querySelectorAll(".eyeball").forEach((el) => {
        gsap.to(el, { height: 2, duration: 0.5 });
      });
    } else if (moods.purple !== "surprised") {
      purpleRef.current?.querySelectorAll(".eyeball").forEach((el) => {
        const size = Number((el as HTMLElement).style.width.replace("px", "")) || 18;
        gsap.to(el, { height: size, duration: 0.3 });
      });
    }

    if (moods.black === "locked") {
      blackRef.current?.querySelectorAll(".eyeball").forEach((el) => {
        gsap.to(el, { height: 2, duration: 0.5 });
      });
    } else if (moods.black !== "surprised") {
      blackRef.current?.querySelectorAll(".eyeball").forEach((el) => {
        const size = Number((el as HTMLElement).style.width.replace("px", "")) || 16;
        gsap.to(el, { height: size, duration: 0.3 });
      });
    }

    if (moods.yellow !== "unlocked") {
      qt.mouthWidth(80);
      qt.mouthHeight(4);
      gsap.to(yellowMouthRef.current, { borderRadius: "9999px", duration: 0.3 });
    } else {
      qt.mouthWidth(40);
      qt.mouthHeight(20);
      gsap.to(yellowMouthRef.current, { borderRadius: "50%", duration: 0.3 });
    }
  }, [moods]);

  useEffect(() => {
    const idleAnimations = [
      () => {
        if (purpleRef.current && blackRef.current && Math.random() > 0.7) {
          gsap.to(purpleFaceRef.current, { x: 10, duration: 0.5, ease: "power2.out", yoyo: true, repeat: 1 });
          gsap.to(blackFaceRef.current, { x: -10, duration: 0.5, ease: "power2.out", yoyo: true, repeat: 1 });
        }
      },
      () => {
        if (orangeRef.current && Math.random() > 0.6) {
          gsap.to(orangeRef.current, { y: -10, duration: 0.4, ease: "back.out(2)", yoyo: true, repeat: 1 });
        }
      },
      () => {
        if (yellowRef.current && Math.random() > 0.5) {
          gsap.to(yellowRef.current, { skewX: 3, duration: 0.3, ease: "power2.inOut", yoyo: true, repeat: 3 });
        }
      },
    ];

    const interval = setInterval(() => {
      if (!stateRef.current.isTyping && !stateRef.current.isShowingPassword) {
        const animation = idleAnimations[Math.floor(Math.random() * idleAnimations.length)];
        animation();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const purpleEyeballs = purpleRef.current?.querySelectorAll(".eyeball");
    if (!purpleEyeballs?.length) return;

    let blinkTimer: ReturnType<typeof setTimeout>;
    const scheduleBlink = () => {
      blinkTimer = setTimeout(() => {
        if (moods.purple === "locked") {
          scheduleBlink();
          return;
        }
        purpleEyeballs.forEach((el) => {
          gsap.to(el, { height: 2, duration: 0.08, ease: "power2.in" });
        });
        setTimeout(() => {
          purpleEyeballs.forEach((el) => {
            const size = Number((el as HTMLElement).style.width.replace("px", "")) || 18;
            gsap.to(el, { height: size, duration: 0.08, ease: "power2.out" });
          });
          scheduleBlink();
        }, 150);
      }, Math.random() * 4000 + 3000);
    };

    scheduleBlink();
    return () => clearTimeout(blinkTimer);
  }, [moods.purple]);

  useEffect(() => {
    const blackEyeballs = blackRef.current?.querySelectorAll(".eyeball");
    if (!blackEyeballs?.length) return;

    let blinkTimer: ReturnType<typeof setTimeout>;
    const scheduleBlink = () => {
      blinkTimer = setTimeout(() => {
        if (moods.black === "locked") {
          scheduleBlink();
          return;
        }
        blackEyeballs.forEach((el) => {
          gsap.to(el, { height: 2, duration: 0.08, ease: "power2.in" });
        });
        setTimeout(() => {
          blackEyeballs.forEach((el) => {
            const size = Number((el as HTMLElement).style.width.replace("px", "")) || 16;
            gsap.to(el, { height: size, duration: 0.08, ease: "power2.out" });
          });
          scheduleBlink();
        }, 150);
      }, Math.random() * 4000 + 3000);
    };

    scheduleBlink();
    return () => clearTimeout(blinkTimer);
  }, [moods.black]);

  const getMoodSymbol = (mood: CharacterMood) => {
    switch (mood) {
      case "hacking": return "<HACK/>";
      case "surprised": return "[!]";
      case "locked": return "[LOCKED]";
      case "unlocked": return "[OPEN]";
      default: return "";
    }
  };

  const renderHackerCharacter = (
    character: string,
    charRef: React.RefObject<HTMLDivElement | null>,
    faceRef: React.RefObject<HTMLDivElement | null>,
    style: { left: string; width: string; height: string; zIndex: number; borderRadius: string },
    colors: typeof HACKER_COLORS.purple,
    eyeSize: string,
    pupilSize: string,
    maxDistance: number,
    facePosition: { left: string; top: string; gap: string },
    hasEyeBall: boolean,
    binaryCode: string,
    hexCode: string,
    extraContent?: React.ReactNode
  ) => {
    return (
      <div
        ref={charRef}
        onClick={() => handleCharacterClick(character)}
        onMouseEnter={() => handleCharacterHover(character, true)}
        onMouseLeave={() => handleCharacterHover(character, false)}
        style={{
          position: "absolute",
          bottom: 0,
          left: style.left,
          width: style.width,
          height: style.height,
          background: colors.bodyGradient,
          borderRadius: style.borderRadius,
          zIndex: style.zIndex,
          transformOrigin: "bottom center",
          willChange: "transform",
          cursor: "pointer",
          boxShadow: colors.glowShadow,
          border: colors.border,
          overflow: "hidden",
        }}
      >
        <div style={{ position: "absolute", inset: 0, background: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.15) 2px, rgba(0,0,0,0.15) 4px)", pointerEvents: "none", zIndex: 10 }} />
        <div style={{ position: "absolute", inset: 0, opacity: 0.1, backgroundImage: `linear-gradient(90deg, ${colors.glow} 1px, transparent 1px), linear-gradient(${colors.glow} 1px, transparent 1px)`, backgroundSize: "20px 20px", pointerEvents: "none" }} />
        
        <div style={{ position: "absolute", top: "6px", left: "8px", fontFamily: "'Courier New', monospace", fontSize: "7px", color: colors.glow, opacity: 0.5, letterSpacing: "1px", pointerEvents: "none", zIndex: 5 }}>
          {binaryCode}
        </div>
        <div style={{ position: "absolute", top: "18px", left: "8px", fontFamily: "'Courier New', monospace", fontSize: "7px", color: colors.glow, opacity: 0.3, letterSpacing: "1px", pointerEvents: "none", zIndex: 5 }}>
          0x{hexCode}
        </div>

        <div style={{ position: "absolute", top: "6px", right: "8px", width: "5px", height: "5px", borderRadius: "50%", backgroundColor: colors.glow, boxShadow: `0 0 6px ${colors.glow}`, animation: "pulse 2s ease-in-out infinite", pointerEvents: "none", zIndex: 5 }} />

        {moods[character] !== "normal" && (
          <div style={{ position: "absolute", top: "18px", right: "6px", fontFamily: "'Courier New', monospace", fontSize: "9px", color: colors.glow, fontWeight: "bold", pointerEvents: "none", zIndex: 5, textShadow: `0 0 8px ${colors.glow}` }}>
            {getMoodSymbol(moods[character])}
          </div>
        )}

        <div ref={faceRef} style={{ position: "absolute", display: "flex", gap: facePosition.gap, left: facePosition.left, top: facePosition.top }}>
          {hasEyeBall ? (
            <>
              <EyeBall size={eyeSize} pupilSize={pupilSize} maxDistance={maxDistance} eyeColor={colors.eyeColor} pupilColor={colors.pupilColor} />
              <EyeBall size={eyeSize} pupilSize={pupilSize} maxDistance={maxDistance} eyeColor={colors.eyeColor} pupilColor={colors.pupilColor} />
            </>
          ) : (
            <>
              <Pupil size={eyeSize} maxDistance={maxDistance} pupilColor={colors.eyeColor} />
              <Pupil size={eyeSize} maxDistance={maxDistance} pupilColor={colors.eyeColor} />
            </>
          )}
        </div>

        {extraContent}

        <div style={{ position: "absolute", bottom: "4px", left: "50%", transform: "translateX(-50%)", display: "flex", gap: "3px", pointerEvents: "none" }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} style={{ width: "10px", height: "2px", backgroundColor: colors.glow, opacity: 0.3 + i * 0.2 }} />
          ))}
        </div>
      </div>
    );
  };

  return (
    <div ref={containerRef} style={{ position: "relative", width: "550px", height: "400px", cursor: "pointer" }}>
      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        @keyframes scan { 0% { transform: translateY(-100%); } 100% { transform: translateY(400px); } }
      `}</style>

      <div style={{ position: "absolute", left: 0, right: 0, height: "2px", background: "linear-gradient(90deg, transparent, rgba(0, 255, 65, 0.3), transparent)", animation: "scan 4s linear infinite", zIndex: 20, pointerEvents: "none" }} />

      {renderHackerCharacter("purple", purpleRef, purpleFaceRef, { left: "70px", width: "180px", height: "400px", zIndex: 1, borderRadius: "10px 10px 0 0" }, HACKER_COLORS.purple, "18px", "7px", 5, { left: "45px", top: "40px", gap: "32px" }, true, binaryCodes.purple, hexCodes.purple)}
      {renderHackerCharacter("black", blackRef, blackFaceRef, { left: "240px", width: "120px", height: "310px", zIndex: 2, borderRadius: "8px 8px 0 0" }, HACKER_COLORS.black, "16px", "6px", 4, { left: "26px", top: "32px", gap: "24px" }, true, binaryCodes.black, hexCodes.black)}
      {renderHackerCharacter("orange", orangeRef, orangeFaceRef, { left: "0", width: "240px", height: "200px", zIndex: 3, borderRadius: "120px 120px 0 0" }, HACKER_COLORS.orange, "12px", "5px", 5, { left: "82px", top: "90px", gap: "32px" }, false, binaryCodes.orange, hexCodes.orange)}
      {renderHackerCharacter("yellow", yellowRef, yellowFaceRef, { left: "310px", width: "140px", height: "230px", zIndex: 4, borderRadius: "70px 70px 0 0" }, HACKER_COLORS.yellow, "12px", "5px", 5, { left: "52px", top: "40px", gap: "24px" }, false, binaryCodes.yellow, hexCodes.yellow,
        <div ref={yellowMouthRef} style={{ position: "absolute", width: "80px", height: "4px", backgroundColor: HACKER_COLORS.yellow.glow, borderRadius: "9999px", left: "40px", top: "88px", boxShadow: `0 0 8px ${HACKER_COLORS.yellow.glow}` }} />
      )}
    </div>
  );
}
