import logging
import asyncio
from pysnmp.hlapi.v3arch.asyncio import *

logger = logging.getLogger(__name__)


class SNMPClient:
    def __init__(self, ip: str, community: str, port: int = 161, timeout: int = 10, retries: int = 3):
        self.ip = ip
        self.community = community
        self.port = port
        self.timeout = timeout
        self.retries = retries

    def get(self, oid: str):
        return asyncio.run(self._get(oid))

    def set(self, oid: str, value):
        return asyncio.run(self._set(oid, value))

    def walk(self, oid: str) -> list:
        return asyncio.run(self._walk(oid))

    async def _get(self, oid: str):
        snmpEngine = SnmpEngine()
        errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
            snmpEngine,
            CommunityData(self.community, mpModel=1),
            await UdpTransportTarget.create((self.ip, self.port), timeout=self.timeout, retries=self.retries),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        snmpEngine.closeDispatcher()

        if errorIndication:
            raise ConnectionError(f"SNMP error en {self.ip}: {errorIndication}")
        if errorStatus:
            raise ValueError(f"SNMP status error: {errorStatus.prettyPrint()}")

        return varBinds[0][1]

    async def _set(self, oid: str, value):
        snmpEngine = SnmpEngine()
        errorIndication, errorStatus, errorIndex, varBinds = await set_cmd(
            snmpEngine,
            CommunityData(self.community, mpModel=1),
            await UdpTransportTarget.create((self.ip, self.port), timeout=self.timeout, retries=self.retries),
            ContextData(),
            ObjectType(ObjectIdentity(oid), value)
        )
        snmpEngine.closeDispatcher()

        if errorIndication:
            raise ConnectionError(f"SNMP set error en {self.ip}: {errorIndication}")
        if errorStatus:
            raise ValueError(f"SNMP set status error: {errorStatus.prettyPrint()}")

        return True

    async def _walk(self, oid: str) -> list:
        results = []
        snmpEngine = SnmpEngine()
        async for errorIndication, errorStatus, errorIndex, varBinds in walk_cmd(
            snmpEngine,
            CommunityData(self.community, mpModel=1),
            await UdpTransportTarget.create((self.ip, self.port), timeout=self.timeout, retries=self.retries),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        ):
            if errorIndication:
                logger.warning(f"Walk error: {errorIndication}")
                break
            if errorStatus:
                logger.warning(f"Walk status error: {errorStatus.prettyPrint()}")
                break
            for varBind in varBinds:
                results.append((str(varBind[0]), varBind[1]))

        snmpEngine.closeDispatcher()
        return results