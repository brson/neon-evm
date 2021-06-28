from solana_utils import *

# from ..eth_tx_utils import make_keccak_instruction_data, make_instruction_data_from_tx, Trx
# from eth_utils import abi
# from web3.auto import w3
from eth_keys import keys as eth_keys
from web3 import Web3
import argparse
from eth_utils import abi
from base58 import b58decode
import random

# CONTRACTS_DIR = os.environ.get("CONTRACTS_DIR", "contracts/")
CONTRACTS_DIR = "contracts/"
# evm_loader_id = os.environ.get("EVM_LOADER")
evm_loader_id = "GWDnHTcNoryfBpLzRFvpicwfBHDJecRyw5Jq3Mo8P6RR"

# sysinstruct = "Sysvar1nstructions1111111111111111111111111"
# keccakprog = "KeccakSecp256k11111111111111111111111111111"
sysvarclock = "SysvarC1ock11111111111111111111111111111111"
contracts_file = "contracts.json"
accounts_file = "accounts.json"


class PerformanceTest():
    @classmethod
    def setUpClass(cls):
        print("\ntest_performance.py setUpClass")

        # wallet = WalletAccount(wallet_path())
        wallet = RandomAccount()
        tx = client.request_airdrop(wallet.acc.public_key(), 10000000 * 10 ** 9)
        confirm_transaction(client, tx['result'])

        cls.loader = EvmLoader(wallet, evm_loader_id)
        cls.acc = wallet.get_acc()

        # Create ethereum account for user account
        cls.caller_ether = eth_keys.PrivateKey(cls.acc.secret_key()).public_key.to_canonical_address()
        (cls.caller, cls.caller_nonce) = cls.loader.ether2program(cls.caller_ether)

        if getBalance(cls.caller) == 0:
            print("Create caller account...")
            _ = cls.loader.createEtherAccount(cls.caller_ether)
            print("Done\n")

        print('Account:', cls.acc.public_key(), bytes(cls.acc.public_key()).hex())
        print("Caller:", cls.caller_ether.hex(), cls.caller_nonce, "->", cls.caller,
              "({})".format(bytes(PublicKey(cls.caller)).hex()))


def check_address_event(result, factory_eth, erc20_eth):
    assert(result['meta']['err'] == None)
    assert(len(result['meta']['innerInstructions']) == 2)
    assert(len(result['meta']['innerInstructions'][1]['instructions']) == 2)
    data = b58decode(result['meta']['innerInstructions'][1]['instructions'][1]['data'])
    assert(data[:1] == b'\x06')  #  OnReturn
    assert(data[1] == 0x11)  # 11 - Machine encountered an explict stop

    data = b58decode(result['meta']['innerInstructions'][1]['instructions'][0]['data'])
    assert(data[:1] == b'\x07')  # 7 means OnEvent
    assert(data[1:21] == factory_eth)
    assert(data[21:29] == bytes().fromhex('%016x' % 1)[::-1])  # topics len
    assert(data[29:61] == abi.event_signature_to_log_topic('Address(address)'))  # topics
    assert(data[61:93] == bytes().fromhex("%024x" % 0)+erc20_eth)  # sum

def check_transfer_event(result, erc20_eth, to, sum):
    assert(result['meta']['err'] == None)
    assert(len(result['meta']['innerInstructions']) == 1)
    assert(len(result['meta']['innerInstructions'][0]['instructions']) == 2)
    data = b58decode(result['meta']['innerInstructions'][0]['instructions'][1]['data'])
    assert(data[:1] == b'\x06')  #  OnReturn
    assert(data[1] == 0x11)  # 11 - Machine encountered an explict stop

    data = b58decode(result['meta']['innerInstructions'][0]['instructions'][0]['data'])
    assert(data[:1] == b'\x07')  # 7 means OnEvent
    assert(data[1:21] == bytes.fromhex(erc20_eth))
    assert(data[21:29] == bytes().fromhex('%016x' % 3)[::-1])  # topics len
    assert(data[29:61] == abi.event_signature_to_log_topic('Transfer(address,address,uint256)'))  # topics
    assert(data[61:93] == bytes().fromhex("%064x" % 0))  # address(0)
    assert(data[93:125] == bytes().fromhex("%024x" % 0) + bytes.fromhex(to))  # to
    assert(data[125:157] == bytes().fromhex("%064x" % sum))  # value

def get_filehash(factory, factory_code, factory_eth):
    trx = Transaction()
    trx.add(
        TransactionInstruction(
            program_id=evm_loader_id,
            data=bytearray.fromhex("03") + abi.function_signature_to_4byte_selector('get_hash()'),
            keys=[
                AccountMeta(pubkey=factory, is_signer=False, is_writable=True),
                AccountMeta(pubkey=factory_code, is_signer=False, is_writable=True),
                AccountMeta(pubkey=instance.acc.public_key(), is_signer=True, is_writable=False),
                AccountMeta(pubkey=evm_loader_id, is_signer=False, is_writable=False),
                AccountMeta(pubkey=PublicKey(sysvarclock), is_signer=False, is_writable=False),
            ]))
    result = send_transaction(client, trx, instance.acc)['result']

    assert(result['meta']['err'] == None)
    assert(len(result['meta']['innerInstructions']) == 1)
    assert(len(result['meta']['innerInstructions'][0]['instructions']) == 2)
    data = b58decode(result['meta']['innerInstructions'][0]['instructions'][1]['data'])
    assert(data[:1] == b'\x06')  #  OnReturn
    assert(data[1] == 0x11)  # 11 - Machine encountered an explict stop

    data = b58decode(result['meta']['innerInstructions'][0]['instructions'][0]['data'])
    assert(data[:1] == b'\x07')  # 7 means OnEvent
    assert(data[1:21] == factory_eth)
    assert(data[21:29] == bytes().fromhex('%016x' % 1)[::-1])  # topics len
    hash = data[61:93]
    return hash


parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--count', metavar="count of the transaction",  type=int,  help='count transaction (>=1)')
parser.add_argument('--step', metavar="step of the test", type=str,  help='deploy, create_acc, create_trx, send_trx')

args = parser.parse_args()

if args.step == "deploy":

    instance = PerformanceTest()
    instance.setUpClass()

    res = instance.loader.deploy(CONTRACTS_DIR + "Factory.binary", instance.caller)
    (factory, factory_eth, factory_code) = (res['programId'], bytes.fromhex(res['ethereum'][2:]), res['codeId'])

    erc20_filehash = get_filehash(factory, factory_code, factory_eth)
    print("factory", factory)
    print ("factory_eth", factory_eth.hex())
    print("factory_code", factory_code)
    func_name = bytearray.fromhex("03") + abi.function_signature_to_4byte_selector('create_erc20(bytes32)')
    receipt_map = {}

    for i in range(args.count):
        print (" -- count", i)
        trx_count = getTransactionCount(client, factory)

        salt = bytes().fromhex("%064x" % int(trx_count + i))
        trx_data = func_name + salt
        erc20_ether = bytes(Web3.keccak(b'\xff' + factory_eth + salt + erc20_filehash)[-20:])

        erc20_id = instance.loader.ether2program(erc20_ether)[0]
        seed = b58encode(bytes.fromhex(erc20_ether.hex()))
        erc20_code = accountWithSeed(instance.acc.public_key(), str(seed, 'utf8'), PublicKey(evm_loader_id))
        print("erc20_id:", erc20_id)
        print("erc20_eth:", erc20_ether.hex())
        print("erc20_code:", erc20_code)

        trx = Transaction()
        trx.add(
            createAccountWithSeed(
                instance.acc.public_key(),
                instance.acc.public_key(),
                str(seed, 'utf8'),
                10 ** 9,
                4000 + 4 * 1024,
                PublicKey(evm_loader_id))
        )
        trx.add(instance.loader.createEtherAccountTrx(erc20_ether, erc20_code)[0])

        trx.add(
            TransactionInstruction(
                program_id=evm_loader_id,
                data=trx_data,
                keys=[
                    AccountMeta(pubkey=factory, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=factory_code, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=instance.acc.public_key(), is_signer=True, is_writable=False),
                    AccountMeta(pubkey=erc20_id, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=erc20_code, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=evm_loader_id, is_signer=False, is_writable=False),
                    AccountMeta(pubkey=PublicKey(sysvarclock), is_signer=False, is_writable=False),
            ]))
        res = client.send_transaction(trx, instance.acc,
                                         opts=TxOpts(skip_confirmation=True, preflight_commitment="confirmed"))

        receipt_map[(str(erc20_id), erc20_ether, str(erc20_code))] = res["result"]

    contracts = []
    for ((erc20_id, erc20_ether, erc20_code), receipt) in receipt_map.items():
        confirm_transaction(client, receipt)
        result = client.get_confirmed_transaction(receipt)
        check_address_event(result['result'], factory_eth, erc20_ether)
        contracts.append((erc20_id, erc20_ether.hex(), erc20_code))

    with open(contracts_file, mode='w') as f:
        f.write(json.dumps(contracts))

elif args.step == "create_acc":

    instance = PerformanceTest()
    instance.setUpClass()

    receipt_map = {}
    for i in range(args.count):
        ether = random.randbytes(20)
        trx = Transaction()
        (transaction, sol_account) = instance.loader.createEtherAccountTrx(ether)
        trx.add(transaction)
        res = client.send_transaction(trx, instance.acc,
                                      opts=TxOpts(skip_confirmation=True, preflight_commitment="confirmed"))
        receipt_map[(ether, sol_account)] = res["result"]

    ether_accounts = []
    for ((ether, sol_account), receipt) in receipt_map.items():
        confirm_transaction(client, receipt)
        result = client.get_confirmed_transaction(receipt)
        print(ether.hex(), sol_account)
        ether_accounts.append((ether.hex(), sol_account))

    with open(accounts_file, mode='w') as f:
        f.write(json.dumps(ether_accounts))

elif args.step == "create_trx":
    instance = PerformanceTest()
    instance.setUpClass()

    with open(contracts_file, mode='r') as f:
        contracts = json.loads(f.read())
    with open(accounts_file, mode='r') as f:
        accounts = json.loads(f.read())

    func_name = bytearray.fromhex("03") + abi.function_signature_to_4byte_selector('mint(address,uint256)')

    receipt_map = {}
    sum = 1000 * 10 ** 18
    for (erc20_sol, erc20_eth_hex, erc20_code) in contracts:
        for (acc_eth_hex, acc_sol) in accounts:
            trx_data = func_name + \
                       bytes().fromhex("%024x" % 0 + acc_eth_hex) + \
                       bytes().fromhex("%064x" % sum)

            trx = Transaction()
            trx.add(
                TransactionInstruction(
                    program_id=evm_loader_id,
                    data=trx_data,
                    keys=[
                        AccountMeta(pubkey=erc20_sol, is_signer=False, is_writable=True),
                        AccountMeta(pubkey=erc20_code, is_signer=False, is_writable=True),
                        AccountMeta(pubkey=instance.acc.public_key(), is_signer=True, is_writable=False),
                        AccountMeta(pubkey=acc_sol, is_signer=False, is_writable=True),
                        AccountMeta(pubkey=evm_loader_id, is_signer=False, is_writable=False),
                        AccountMeta(pubkey=PublicKey(sysvarclock), is_signer=False, is_writable=False),
                ]))
            res = client.send_transaction(trx, instance.acc,
                                             opts=TxOpts(skip_confirmation=True, preflight_commitment="confirmed"))

            receipt_map[(erc20_eth_hex, acc_eth_hex)] = res["result"]

    for ((erc20_eth_hex, acc_eth_hex), receipt) in receipt_map.items():
        confirm_transaction(client, receipt)
        res = client.get_confirmed_transaction(receipt)
        check_transfer_event(res['result'], erc20_eth_hex, acc_eth_hex, sum)
 